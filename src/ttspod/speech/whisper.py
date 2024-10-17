"""generate audio using whisperspeech model"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
try:
    from warnings import simplefilter  # disable coqui future warnings
    simplefilter(action='ignore', category=FutureWarning)
    from contextlib import redirect_stdout, redirect_stderr
    from nltk import sent_tokenize
    from glob import glob
    import numpy as np
    from os import path, environ as env
    import torch
    import torchaudio
    from pathlib import Path
    from platform import processor
    import torch
    from transformers import pytorch_utils
    from whisperspeech.pipeline import Pipeline
    from io import StringIO
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# ttspod modules
from logger import Logger
from util import patched_isin_mps_friendly, chunk

# this attempts to minimize random voice variations
torch.manual_seed(123456789)

# sensible default settings if none are provided
DEVICE = 'cpu'

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


class Whisper:
    """whisper text to speech generator"""

    def __init__(self, config=None, log=None, t2s_model=None, s2a_model=None, voice=None, gpu='gpu'):
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.voice = None
        if not config:
            c = {}
        else:
            if not isinstance(config, dict):
                c = vars(config)
            else:
                c = config
        if gpu == 'cpu':
            self.gpu = 'cpu'
        else:
            self.gpu = DEVICE
        t2s_model = c.get(
            'whisper_t2s_model', 'whisperspeech/whisperspeech:t2s-base-en+pl.model')
        s2a_model = c.get(
            'whisper_a2s_model', 'whisperspeech/whisperspeech:s2a-q4-base-en+pl.model')
        voice = path.expanduser(voice if voice else c.get('voice', ''))
        if path.isfile(voice):
            self.voice = voice
        elif path.isdir(voice):
            audio_files = glob(path.join(voice, "*wav")) + \
                glob(path.join(voice, "*mp3"))
            if audio_files:
                self.voice = audio_files[0]
        self.tts = Pipeline(t2s_ref=t2s_model,
                            s2a_ref=s2a_model,
                            device=self.gpu,
                            torch_compile=False,
                            optimize=True)
        self.log.write('Whisper generator initialized.',error=False,log_level=2)

    def generate(self, texts=None, cps=15, output=None, speaker=None):
        """main whisperspeech generator"""
        if not speaker:
            self.log.write('using default speaker')
            speaker = self.tts.default_speaker
        elif isinstance(speaker, (str, Path)):
            self.log.write(f'extracting speaker {speaker}')
            speaker = self.tts.extract_spk_emb(speaker)
        atoks = []
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        for i, text in enumerate(texts):
            self.log.write(
                f'Processing chunk {i+1} of {len(texts)}:\n{text}',
                error=False,
                log_level=3)
            try:
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                    r = self.tts.generate_atoks(
                        text=text,
                        speaker=speaker,
                        lang='en',
                        cps=cps,
                        step_callback=None
                    )
            except Exception as err:
                self.log.write(f'Something went wrong: {err}')
            atoks.append(r)
        result = stdout_buffer.getvalue()+"\n"+stderr_buffer.getvalue()
        try:
            audios = []
            for i, atok in enumerate(atoks):
                if i != 0:
                    audios.append(torch.zeros((1, int(24000*0.5)),
                                              dtype=atok.dtype, device=self.gpu))
                audios.append(self.tts.vocoder.decode(atok))
            if output:
                torchaudio.save(output, torch.cat(audios, -1).cpu(), 24000)
                if path.isfile(output):
                    return True
        except Exception as err:
            self.log.write(f'Something went wrong: {err}\n{result}')

    def convert(self, text, output_file):
        """convert text input to given output_file"""
        chunks = chunk(text)
        try:
            results = self.generate(
                texts=chunks, output=output_file, speaker=self.voice)
            if results:
                self.log.write(
                    f'TTS conversion complete: {results}')
                return True
            else:
                return False
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(f'TTS conversion failed: {err}', True)
            return False


if __name__ == "__main__":
    whisper = Whisper()

    # TEXT = """A Hare was making fun of the Tortoise one day for being so slow.
    # "Do you ever get anywhere?" he asked with a mocking laugh.
    # "Yes," replied the Tortoise, "and I get there sooner than you think. I'll run you a race and prove it."
    # The Hare was much amused at the idea of running a race with the Tortoise, but for the fun of the thing he agreed. So the Fox, who had consented to act as judge, marked the distance and started the runners off.
    # The Hare was soon far out of sight, and to make the Tortoise feel very deeply how ridiculous it was for him to try a race with a Hare, he lay down beside the course to take a nap until the Tortoise should catch up.
    # The Tortoise meanwhile kept going slowly but steadily, and, after a time, passed the place where the Hare was sleeping. But the Hare slept on very peacefully; and when at last he did wake up, the Tortoise was near the goal. The Hare now ran his swiftest, but he could not overtake the Tortoise in time.
    # """
    # whisper = Whisper(voice='~/ttspod/working/voices/it')
    # whisper.convert(TEXT, "whisper-test.mp3")
