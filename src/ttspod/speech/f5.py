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
    from f5_tts.model import CFM, DiT
    from f5_tts.model.utils import (get_tokenizer, load_checkpoint)
    from glob import glob
    from os import path, environ as env
    # from os import environ as env
    # from pathlib import Path
    # from platform import processor
    from pprint import pprint
    from pydub import AudioSegment, silence
    from transformers import pipeline  # , pytorch_utils
    from vocos import Vocos
    import numpy as np
    import re
    import soundfile as sf
    import tempfile
    import torch
    import torchaudio
    import tqdm
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# ttspod modules
from logger import Logger
from util import chunk  # , patched_isin_mps_friendly

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
elif torch.backends.mps.is_available():
    # elif torch.backends.mps.is_available() and processor() != 'i386':
    DEVICE = 'mps'
    env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    # pytorch_utils.isin_mps_friendly = patched_isin_mps_friendly

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
        non_silent_wave = AudioSegment.silent(duration=0)
        for non_silent_segment in non_silent_segments:
            non_silent_wave += non_silent_segment
        audio_clip = non_silent_wave

        audio_duration = len(audio_clip)
        if audio_duration > 15000:
            audio_clip = audio_clip[:15000]
        audio_clip.export(f.name, format="wav")
        ref_audio = f.name

    if not ref_text.strip():
        pipe = pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-large-v3-turbo",
            torch_dtype=torch.float16,
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


def load_model(repo_name, exp_name, model_cls, model_cfg, ckpt_step):
    """load F5 TTS model"""
    checkpoint_path = str(cached_path(
        f"hf://SWivid/{repo_name}/{exp_name}/model_{ckpt_step}.safetensors"))
    vocab_char_map, vocab_size = get_tokenizer("Emilia_ZH_EN", "pinyin")
    model = CFM(
        transformer=model_cls(
            **model_cfg, text_num_embeds=vocab_size, mel_dim=N_MEL_CHANNELS
        ),
        mel_spec_kwargs=dict(
            target_sample_rate=SAMPLE_RATE,
            n_mel_channels=N_MEL_CHANNELS,
            hop_length=HOP_LENGTH,
        ),
        odeint_kwargs=dict(
            method=ODE_METHOD,
        ),
        vocab_char_map=vocab_char_map,
    ).to(DEVICE)
    model = load_checkpoint(
        model=model, ckpt_path=checkpoint_path, device=DEVICE, use_ema=True)
    return model


class F5:
    """F5 TTS generator"""

    def __init__(self, config=None, log=None, voice=None) -> None:
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
        (self.ref_audio, self.ref_text) = process_voice(voice)
        self.audio, self.sr = torchaudio.load(self.ref_audio)
        self.max_chars = int(len(self.ref_text.encode('utf-8')) /
                             (self.audio.shape[-1] / self.sr) *
                             (25 - self.audio.shape[-1] / self.sr))
        self.vocos = Vocos.from_pretrained("charactr/vocos-mel-24khz")
        self.ema_model = load_model(MODEL, "F5TTS_Base", DiT,
                                    F5TTS_model_cfg, 1200000)

    def infer_batch(self, ref_audio, ref_text, gen_text_batches, cross_fade_duration=0.15):
        """workhorse inference function"""
        audio, sr = ref_audio
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
            self.log.write(f'Chunk {i}: {gen_text}', log_level=3)
            if len(ref_text[-1].encode('utf-8')) == 1:
                ref_text = ref_text + " "
            final_text_list = [ref_text + gen_text]

            # Calculate duration
            ref_audio_len = audio.shape[-1] // HOP_LENGTH
            punctuation = r"。，、；：？！."
            ref_text_len = len(ref_text.encode('utf-8')) + 3 * \
                len(re.findall(punctuation, ref_text))
            gen_text_len = len(gen_text.encode('utf-8')) + 3 * \
                len(re.findall(punctuation, gen_text))
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

            generated = generated[:, ref_audio_len:, :]
            generated_mel_spec = rearrange(generated, "1 n d -> 1 d n")
            generated_wave = self.vocos.decode(generated_mel_spec.cpu())
            if rms < TARGET_RMS:
                generated_wave = generated_wave * rms / TARGET_RMS
            generated_wave = generated_wave.squeeze().cpu().numpy()
            generated_waves.append(generated_wave)

        # Combine all generated waves with cross-fading
        if cross_fade_duration <= 0:
            # Simply concatenate
            final_wave = np.concatenate(generated_waves)
        else:
            final_wave = generated_waves[0]
            for i in range(1, len(generated_waves)):
                prev_wave = final_wave
                next_wave = generated_waves[i]

                # Calculate cross-fade samples, ensuring it does not exceed wave lengths
                cross_fade_samples = int(cross_fade_duration * SAMPLE_RATE)
                cross_fade_samples = min(
                    cross_fade_samples, len(prev_wave), len(next_wave))

                if cross_fade_samples <= 0:
                    # No overlap possible, concatenate
                    final_wave = np.concatenate([prev_wave, next_wave])
                    continue

                # Overlapping parts
                prev_overlap = prev_wave[-cross_fade_samples:]
                next_overlap = next_wave[:cross_fade_samples]

                # Fade out and fade in
                fade_out = np.linspace(1, 0, cross_fade_samples)
                fade_in = np.linspace(0, 1, cross_fade_samples)

                # Cross-faded overlap
                cross_faded_overlap = prev_overlap * fade_out + next_overlap * fade_in

                # Combine
                new_wave = np.concatenate([
                    prev_wave[:-cross_fade_samples],
                    cross_faded_overlap,
                    next_wave[cross_fade_samples:]
                ])

                final_wave = new_wave

        return final_wave

    def convert(self, text="", output_file=None):
        """convert text input to given output_file"""
        chunks = chunk(text=text, min_length=round(
            self.max_chars/2), max_length=self.max_chars)
        result = self.infer_batch(
            (self.audio, self.sr), self.ref_text, chunks, 0.15)
        if output_file:
            try:
                f = open(output_file, "wb")
                sf.write(f.name, result, SAMPLE_RATE, format="mp3")
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
    # f5.convert(text=TEXT, output_file="f5-test.mp3")
