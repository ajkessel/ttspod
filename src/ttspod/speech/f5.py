"""generate audio using f5-tts model"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
try:
    from warnings import simplefilter
    from cached_path import cached_path
    from importlib.resources import files
    from einops import rearrange
    from f5_tts.model import DiT
    from f5_tts.infer.utils_infer import load_model, preprocess_ref_audio_text
    from glob import glob
    from os import path, environ as env
    from platform import processor
    from pprint import pprint
    from pydub import AudioSegment, silence
    from transformers import pipeline, pytorch_utils
    from vocos import Vocos
    import numpy as np
    import soundfile as sf
    import tempfile
    import torch
    import torchaudio
    import tqdm
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# ttspod modules
from logger import Logger
from util import chunk, patched_isin_mps_friendly

simplefilter(action='ignore', category=FutureWarning)

# sensible default settings if none are provided
DEVICE = 'cpu'
MODEL = 'F5-TTS'
F5TTS_model_cfg = dict(
    dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4
)
SAMPLE_RATE = 24000
N_MEL_CHANNELS = 100
HOP_LENGTH = 256
TARGET_RMS = 0.1
NFE_STEP = 32  # 16, 32
CFG_STRENGTH = 2.0
ODE_METHOD = "euler"
SWAY_SAMPLING_COEF = -1.0
SPEED = 1.0

if torch.cuda.is_available():
    DEVICE = "cuda"
elif torch.backends.mps.is_available() and processor() != 'i386':
    DEVICE = 'mps'
    env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    pytorch_utils.isin_mps_friendly = patched_isin_mps_friendly

# cspell: disable
if "cuda" in DEVICE and torch.cuda.get_device_name().endswith("[ZLUDA]"):
    torch.backends.cudnn.enabled = False
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
# cspell: enable


def process_voice(ref_audio_orig, ref_text=""):
    """generate reference text from audio clip for cloning"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        audio_clip = AudioSegment.from_file(ref_audio_orig)

        non_silent_segments = silence.split_on_silence(
            audio_clip, min_silence_len=1000, silence_thresh=-50, keep_silence=1000)
        audio_clip = AudioSegment.silent(duration=0)
        for non_silent_segment in non_silent_segments:
            audio_clip += non_silent_segment
            if len(audio_clip) > 15000:
                break

        audio_duration = len(audio_clip)
        if audio_duration > 20000:
            audio_clip = audio_clip[:20000]
        audio_clip.export(f.name, format="wav")
        ref_audio = f.name

    if not ref_text.strip():
        pipe = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-large-v3-turbo",
            torch_dtype=torch.float16 if DEVICE != 'cpu' else torch.float32,
            device=DEVICE,
        )
        ref_text = pipe(
            ref_audio,
            chunk_length_s=30,
            batch_size=128,
            # generate_kwargs={"task": "transcribe"},
            return_timestamps=False,
        )["text"].strip()
    return ref_audio, ref_text


# def load_model(repo_name, exp_name, model_cls, model_cfg, ckpt_step):
#     """load F5 TTS model"""
#     # checkpoint_path = files('f5_tts').joinpath('data','Emilia_ZH_EN_pinyin')
#     checkpoint_path = str(cached_path(
#         f"hf://SWivid/{repo_name}/{exp_name}/model_{ckpt_step}.safetensors"))

#     vocab_char_map, vocab_size = get_tokenizer("Emilia_ZH_EN", "pinyin")
#     model = CFM(
#         transformer=model_cls(
#             **model_cfg, text_num_embeds=vocab_size, mel_dim=N_MEL_CHANNELS
#         ),
#         mel_spec_kwargs=dict(
#             target_sample_rate=SAMPLE_RATE,
#             n_mel_channels=N_MEL_CHANNELS,
#             hop_length=HOP_LENGTH,
#         ),
#         odeint_kwargs=dict(
#             method=ODE_METHOD,
#         ),
#         vocab_char_map=vocab_char_map,
#     ).to(DEVICE)
#     model = load_checkpoint(
#         model=model, ckpt_path=checkpoint_path, device=DEVICE, use_ema=True)
#     return model


class F5:
    """F5 TTS generator"""

    def __init__(self, config=None, log=None, voice="") -> None:
        self.log = log if log else Logger(debug=True)
        self.log.write('F5 TTS initializing.')
        if not voice and isinstance(config, object) and getattr(config, 'voice', ''):
            voice = config.voice
        if path.isdir(voice):
            audio_files = glob(path.join(voice, "*wav")) + \
                glob(path.join(voice, "*mp3"))
            if audio_files:
                voice = audio_files[0]
            else:
                voice = None
        if not voice or not path.exists(voice):
            self.log.write(
                'No voice found, using default voice instead.', error=False, log_level=2)
            voice = files('ttspod').joinpath('data', 'sample.wav')
        self.log.write(f'Using voice: {voice}.')
        assert path.exists(voice)  # some voice must be specified
        (self.ref_audio, self.ref_text) = preprocess_ref_audio_text(
            ref_audio_orig=voice,
            ref_text=""
        )
        self.log.write(
            f'Transcribed {self.ref_audio} to:\n{self.ref_text}.', log_level=3)
        self.audio, self.sr = torchaudio.load(self.ref_audio)
        self.max_chars = int(len(self.ref_text.encode('utf-8')) /
                             (self.audio.shape[-1] / self.sr) *
                             (25 - self.audio.shape[-1] / self.sr))
        self.vocos = Vocos.from_pretrained("charactr/vocos-mel-24khz")
        self.ema_model = load_model(model_cls=DiT,
                                    model_cfg=F5TTS_model_cfg,
                                    ckpt_path=str(cached_path(
                                        f"hf://SWivid/{MODEL}/F5TTS_Base/model_1200000.safetensors")
                                    ),
                                    vocab_file="",
                                    ode_method="euler",
                                    use_ema=True,
                                    device=DEVICE)

    def infer_batch(self, ref_audio, ref_text, gen_text_batches):
        """workhorse inference function"""
        audio, sr = ref_audio

        if not ref_text.endswith(". "):
            if ref_text.endswith("."):
                ref_text += " "
            else:
                ref_text += ". "

        if len(ref_text[-1].encode('utf-8')) == 1:
            ref_text = ref_text + " "

        if audio.shape[0] > 1:
            audio = torch.mean(audio, dim=0, keepdim=True)

        rms = torch.sqrt(torch.mean(torch.square(audio)))
        if rms < TARGET_RMS:
            audio = audio * TARGET_RMS / rms
        if sr != SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(sr, SAMPLE_RATE)
            audio = resampler(audio)
        audio = audio.to(DEVICE)

        generated_waves = []

        for i, gen_text in enumerate(tqdm.tqdm(gen_text_batches)):
            self.log.write(
                f'Chunk {i+1} of {len(gen_text_batches)}: {gen_text}', log_level=3)
            final_text_list = [ref_text + gen_text]

            # Calculate duration
            ref_audio_len = audio.shape[-1] // HOP_LENGTH
            ref_text_len = len(ref_text.encode('utf-8'))
            gen_text_len = len(gen_text.encode('utf-8'))
            duration = ref_audio_len + \
                int(ref_audio_len / ref_text_len * gen_text_len / SPEED)
            # inference
            with torch.inference_mode():
                generated, _ = self.ema_model.sample(
                    cond=audio,
                    text=final_text_list,
                    duration=duration,
                    steps=NFE_STEP,
                    cfg_strength=CFG_STRENGTH,
                    sway_sampling_coef=SWAY_SAMPLING_COEF,
                )
            generated = generated.to(torch.float32)
            generated = generated[:, ref_audio_len:, :]
            generated_mel_spec = rearrange(generated, "1 n d -> 1 d n")
            generated_wave = self.vocos.decode(generated_mel_spec.cpu())
            if rms < TARGET_RMS:
                generated_wave = generated_wave * rms / TARGET_RMS
            generated_wave = generated_wave.squeeze().cpu().numpy()
            generated_waves.append(generated_wave)
        final_wave = np.concatenate(generated_waves)
        return final_wave

    def convert(self, text="", output_file=None):
        """convert text input to given output_file"""
        chunks = chunk(text=text, min_length=round(
            self.max_chars/2), max_length=self.max_chars)
        result = self.infer_batch(
            (self.audio, self.sr), self.ref_text, chunks)
        if output_file:
            try:
                f = open(output_file, "wb")
                sf.write(f.name, result, SAMPLE_RATE, format="mp3")
                audio_segment = AudioSegment.from_file(output_file)
                non_silent_segments = silence.split_on_silence(
                    audio_segment, min_silence_len=1000, silence_thresh=-50, keep_silence=500)
                final_audio = AudioSegment.silent(duration=0)
                for non_silent_segment in non_silent_segments:
                    final_audio += non_silent_segment
                final_audio.export(output_file, format="mp3")
            except Exception:  # pylint: disable=broad-except
                self.log.write(
                    f'Error saving to output_file {output_file}.', error=True, log_level=0)


if __name__ == "__main__":
    f5 = F5()
    print("This is the TTSPod F5 TTS module."
          "It is not intended to run separately except for debugging.")
    pprint(vars(f5))
    pprint(dir(f5))
    # pylint: disable=line-too-long
    # TEXT = """A Hare was making fun of the tortoise one day for being so slow.
    # Do you ever get anywhere? he asked with a mocking laugh.
    # Yes, replied the tortoise, and I get there sooner than you think. I'll run you a race and prove it.
    # The Hare was much amused at the idea of running a race with the tortoise, but for the fun of the thing he agreed.
    # So the Fox, who had consented to act as judge, marked the distance and started the runners off.
    # The Hare was soon far out of sight, and to make the tortoise feel very deeply how ridiculous it was for him to try a race with a Hare, he lay down beside the course to take a nap until the tortoise should catch up.
    # The tortoise meanwhile kept going slowly but steadily, and, after a time, passed the place where the Hare was sleeping. But the Hare slept on very peacefully; and when at last he did wake up, the tortoise was near the goal. The Hare now ran his swiftest, but he could not overtake the tortoise in time.
    # """
    # from time import time
    # f5 = F5(voice='/home/adam/ttspod/working/voices/british-reader/british-reader.wav')
    # start_time = time()
    # f5.convert(text=TEXT, output_file="f5-test.mp3")
    # elapsed_time = round(time()-start_time)
    # print(f'Elapsed time: {elapsed_time}.\n')
