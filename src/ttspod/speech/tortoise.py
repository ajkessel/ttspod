"""Tortoise generator"""
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
try:
    from io import StringIO
    from os import path, environ as env
    from platform import processor
    from pprint import pprint
    from warnings import simplefilter
    from TTS.api import TTS
    from transformers import pytorch_utils
    from contextlib import redirect_stdout, redirect_stderr
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

# suppress spurious FutureWarning from Coqui
simplefilter(action='ignore', category=FutureWarning)

# this attempts to minimize random voice variations
torch.manual_seed(123456789)

# sensible default settings if none are provided
MODEL = 'tts_models/en/multi-dataset/tortoise-v2'
TEMPERATURE = 0.2
DEVICE = 'cpu'
PRESET = 'fast'

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


class Tortoise:
    """generator for Tortoise model"""

    def __init__(self, config=None, log=None, voice_dir=None, voice_name=None, gpu='gpu'):
        self.log = log if log else Logger(debug=True)
        self.config = config
        api = TTS(MODEL, progress_bar=False)
        self.model = api.synthesizer.tts_model
        self.tortoise_config = self.model.config
        if gpu == 'cpu':
            self.model.to('cpu')
        else:
            self.model.to(DEVICE)
        self.voice_dir = voice_dir
        self.voice_name = voice_name
        self.silence = torch.zeros(int(24000*0.5)).unsqueeze(0).cpu()
        self.log.write('Tortoise generator initialized.',
                       error=False, log_level=2)

    def generate(self, texts=None, output=None):
        """convert a list of texts into an output file"""
        audio_segments = []
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        seed = None
        for i, text in enumerate(texts):
            self.log.write(
                f'Processing chunk {i+1} of {len(texts)}:\n{text}',
                error=False,
                log_level=3)
            try:
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    out = self.model.synthesize(
                        text=text,
                        config=self.tortoise_config,
                        speaker_id=self.voice_name,
                        voice_dirs=self.voice_dir,
                        preset=PRESET,
                        use_deterministic_seed=seed,
                        return_deterministic_state=True
                    )
                seed = out['deterministic_seed']
                audio = out['wav'].squeeze(0).cpu()
                audio_segments.append(audio)
                audio_segments.append(self.silence)
            except Exception as e:  # pylint: disable=broad-except
                self.log.write(
                    f'Something went wrong processing {text}: {e}', error=True, log_level=0)
                self.log.write(stdout_buffer.getvalue()+"\n" +
                               stderr_buffer.getvalue(), error=True, log_level=0)
        # TODO: print result in case of failure
        _ = stdout_buffer.getvalue()+"\n"+stderr_buffer.getvalue()
        final_audio = torch.cat(audio_segments, dim=1)
        torchaudio.save(uri=output, src=final_audio,
                        sample_rate=24000, format="mp3")
        if path.isfile(output):
            return output
        else:
            return None


if __name__ == "__main__":
    print("This is the TTSPod Tortoise TTS module. "
          "It is not intended to be run separately except for debugging.")
    tts = Tortoise()
    pprint(vars(tts))
    pprint(dir(tts))

# pylint: disable=line-too-long
    # TEXT = """A Hare was making fun of the Tortoise one day for being so slow.
    # "Do you ever get anywhere?" he asked with a mocking laugh.
    # "Yes," replied the Tortoise, "and I get there sooner than you think. I'll run you a race and prove it."
    # The Hare was much amused at the idea of running a race with the Tortoise, but for the fun of the thing he agreed. So the Fox, who had consented to act as judge, marked the distance and started the runners off.
    # The Hare was soon far out of sight, and to make the Tortoise feel very deeply how ridiculous it was for him to try a race with a Hare, he lay down beside the course to take a nap until the Tortoise should catch up.
    # The Tortoise meanwhile kept going slowly but steadily, and, after a time, passed the place where the Hare was sleeping. But the Hare slept on very peacefully; and when at last he did wake up, the Tortoise was near the goal. The Hare now ran his swiftest, but he could not overtake the Tortoise in time.
    # """
    # tts = Whisper(voice='~/ttspod/working/voices/it')
    # tts.convert(TEXT, "whisper-test.mp3")
