"""generate audio using coqui model"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
try:
    from glob import glob
    from os import path
    from pathlib import Path
    from pprint import pprint
    from warnings import simplefilter  # disable coqui future warnings
    simplefilter(action='ignore', category=FutureWarning)
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# ttspod modules
from logger import Logger
from util import chunk
from xtts import Xtts
from tortoise import Tortoise

MODEL = 'xtts'


class Coqui:
    """coqui text to speech generator"""

    def __init__(self, config=None, log=None, model=None, voice=None, gpu=1):
        self.log = log if log else Logger(debug=True)
        self.config = config
        if not config:
            c = {}
        else:
            if not isinstance(config, dict):
                c = vars(config)
            else:
                c = config
        gpu = 'gpu'
        if c.get('gpu', 1) == 0 or gpu == 0:
            self.log.write('overriding GPU detection, processing on CPU')
            gpu = 'cpu'
        model = model if model else c.get('model', MODEL)
        voice = voice if voice else c.get('voice')
        voices = voice
        voice_dir = None
        voice_name = None
        if voice:
            voice = path.expanduser(str(voice))
        if path.isfile(str(voice)):
            voices = [voice]
            voice_path = path.dirname(voice)
            voice_dir = Path(voice_path).parent
            voice_name = path.basename(voice_path)
        elif path.isdir(str(voice)):
            voices = glob(path.join(voice, "*wav"))
            voice_dir = Path(voice).parent
            voice_name = path.basename(voice)
        match model.lower():
            case 'xtts':
                self.tts = Xtts(config=self.config,
                                log=self.log, voices=voices, gpu=gpu)
            case 'tortoise':
                self.tts = Tortoise(config=self.config, log=self.log,
                                    voice_dir=voice_dir, voice_name=voice_name, gpu=gpu)
            case _:
                raise ValueError(f'model {model} not available')

    def convert(self, text, output_file):
        """convert text input to given output_file"""
        chunks = chunk(text, min_length=100, max_length=250)
        self.log.write(
            f'Starting TTS generation on {len(chunks)} chunks of text.', error=False, log_level=3)
        self.tts.generate(texts=chunks, output=output_file)
        self.log.write('TTS generation completed.', error=False, log_level=3)
        return output_file


if __name__ == "__main__":
    coqui = Coqui()
    print("This is the TTSPod Coqui TTS module.")
    pprint(vars(coqui))
    pprint(dir(coqui))
