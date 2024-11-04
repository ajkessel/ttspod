"""Xtts generator"""
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
try:
    from os import environ as env
    from platform import processor
    from pprint import pprint
    from warnings import simplefilter
    from TTS.api import TTS
    from transformers import pytorch_utils
    import torch
    import torchaudio
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

from util import patched_isin_mps_friendly
from logger import Logger
simplefilter(action='ignore', category=FutureWarning)

# this attempts to minimize random voice variations
torch.manual_seed(123456789)

# sensible default settings if none are provided
MODEL = 'tts_models--multilingual--multi-dataset--xtts_v2'
TEMPERATURE = 0.2
DEVICE = 'cpu'
VOICE = 'Ana Florence'

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


class Xtts:
    """generator for XttsV2 model"""

    def __init__(self, config=None, log=None, voices=None, gpu='gpu'):
        self.log = log if log else Logger(debug=True)
        self.config = config
        api = TTS(MODEL)
        if voices:
            self.voices = voices
        self.model = api.synthesizer.tts_model
        if gpu == 'cpu':
            self.model.to('cpu')
        else:
            self.model.to(DEVICE)
        self.silence = torch.zeros(int(24000*0.5))
        self.speaker_id = None
        if not voices:
            voices = VOICE
        # TODO: sanity check voice availability with fallback
        if isinstance(voices, list):
            self.gpt_cond_latent, self.speaker_embedding = \
                self.model.get_conditioning_latents(audio_path=self.voices)
        elif isinstance(voices, str):
            self.gpt_cond_latent, self.speaker_embedding = \
                self.model.speaker_manager.speakers[voices].values()
        self.log.write('Xtts generator initialized.',error=False,log_level=2)

    def generate(self, texts=None, output=None):
        """convert a list of texts into an output file"""
        audio_segments = []
        for i, text in enumerate(texts):
            self.log.write(
                f'Processing chunk {i+1} of {len(texts)}:\n{text}',
                error=False,
                log_level=3)
            out = self.model.inference(
                text=text,
                language="en",  # TODO configure or detect language
                gpt_cond_latent=self.gpt_cond_latent,
                speaker_embedding=self.speaker_embedding,
                temperature=TEMPERATURE,
                enable_text_splitting=True
            )
            audio_segments.append(torch.tensor(out["wav"]).unsqueeze(0))
            audio_segments.append(self.silence.unsqueeze(0))
        final_audio = torch.cat(audio_segments, dim=1)
        torchaudio.save(output, final_audio, 24000, format="mp3")
        # TODO sanity check that it actually worked

if __name__ == "__main__":
    xtts = Xtts()
    print("This is the TTSPod XTTS TTS module.")
    pprint(vars(xtts))
    pprint(dir(xtts))
