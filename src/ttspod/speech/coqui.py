"""generate audio using coqui model"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
try:
    from contextlib import redirect_stdout, redirect_stderr
    from glob import glob
    from io import BytesIO
    from os import path, environ as env
    from pathlib import Path
    from platform import processor
    from pydub import AudioSegment
    from torch import cuda
    from torch.backends import mps
    from transformers import pytorch_utils
    from TTS.api import TTS
    from warnings import simplefilter  # disable coqui future warnings
    import io
    simplefilter(action='ignore', category=FutureWarning)
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# ttspod modules
from ttspod.logger import Logger
from ttspod.util import patched_isin_mps_friendly

MODEL = 'xtts'
VOICE = 'Aaron Dreschner'
TORTOISE_ARGS = {'kv_cache': True, 'high_vram': True}


class Coqui:
    """coqui text to speech generator"""

    def __init__(self, config=None, log=None, model=None, voice=None, gpu=None):
        self.log = log if log else Logger(debug=True)
        self.config = config
        if cuda.is_available():
            self.cpu = 'cuda'
        elif mps.is_available():
            self.cpu = 'mps'
            env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
            pytorch_utils.isin_mps_friendly = patched_isin_mps_friendly
            if processor() == 'i386':  # hack for older Macs; mps does not appear to work
                self.cpu = 'cpu'
        else:
            self.cpu = 'cpu'
        if gpu==0 or config.gpu==0: # override GPU detection with ttspod_gpu=0
            self.cpu = 'cpu'
        if not config:
            c = {}
        else:
            if not isinstance(config, dict):
                c = vars(config)
            else:
                c = config
        model_parameters_base = {'progress_bar': False}
        generate_parameters_base = {'split_sentences': True}
        model = model if model else c.get('model', MODEL)
        voice = path.expanduser(voice if voice else c.get('voice', ''))
        speaker_id = None
        if path.isfile(voice):
            voice_subdir, _ = path.split(voice)
            voice_dir = str(Path(voice_subdir).parent.absolute())
            voice_name = path.basename(path.normpath(voice_subdir))
            voices = [voice]
        elif path.isdir(voice):
            voice_dir = str(Path(voice).parent.absolute())
            voice_name = path.basename(path.normpath(Path(voice).absolute()))
            voices = glob(path.join(voice, "*wav"))
        else:
            voices = None
            voice_dir = None
            voice_name = None
            speaker_id = voice if voice else VOICE
        self.log.write(f'using voice {voice} {speaker_id}')
        match model.lower():
            case 'xtts':
                model_parameters_extra = {
                    "model_name": "tts_models/multilingual/multi-dataset/xtts_v2"
                }
                generate_parameters_extra = {
                    'speaker_wav': voices,
                    'speaker': speaker_id,
                    'language': 'en'
                }
            case 'tortoise':
                model_parameters_extra = {
                    "model_name": "tts_models/en/multi-dataset/tortoise-v2"
                }
                generate_parameters_extra = {
                    'voice_dir': voice_dir,
                    'speaker': voice_name,
                    'preset': 'fast',
                    'kwargs': {**TORTOISE_ARGS, 'device': self.cpu}
                }
            case _:
                raise ValueError(f'model {model} not available')
        model_parameters = {
            **model_parameters_base,
            **model_parameters_extra
        }
        self.generate_parameters = {
            **generate_parameters_base,
            **generate_parameters_extra
        }
        self.log.write('TTS generation started with settings: '
                       f'{model_parameters} {self.generate_parameters}')
        self.tts = TTS(**model_parameters).to(self.cpu)

    def convert(self, text, output_file):
        """convert text input to given output_file"""
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        wav_buffer = BytesIO()
        self.generate_parameters['text'] = text
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                output_wav = self.tts.tts(**self.generate_parameters)
                self.tts.synthesizer.save_wav(wav=output_wav, path=wav_buffer)
                wav_buffer.seek(0)
            recording = AudioSegment.from_file(wav_buffer, format="wav")
            recording.export(output_file, format='mp3')
            return stdout_buffer.getvalue()+"\n"+stderr_buffer.getvalue()
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(f'TTS conversion failed: {err}', True)


if __name__ == "__main__":
    coqui = Coqui()
    print(coqui)
