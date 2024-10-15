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
from ..logger import Logger
from ..util import patched_isin_mps_friendly

MODEL = 'xtts'
VOICE_XTTS = 'Aaron Dreschner'
VOICE_TORTOISE = 'daniel'
#TORTOISE_ARGS = {'kv_cache': True, 'high_vram': True} # TODO: not working currently
TORTOISE_ARGS = { }


class Coqui:
    """coqui text to speech generator"""

    def __init__(self, config=None, log=None, model=None, voice=None, gpu=1):
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
        if config.gpu == 0 or gpu == 0:
            self.log.write('overriding GPU detection, processing on CPU')
            self.cpu = 'cpu'
        if not config:
            c = {}
        else:
            if not isinstance(config, dict):
                c = vars(config)
            else:
                c = config
        model_parameters_base = {'progress_bar': False }
        generate_parameters_base = {'split_sentences': True}
        model = model if model else c.get('model', MODEL)
        voice = voice if voice else c.get('voice', '')
        if voice:
            voice = path.expanduser(str(voice))
        if path.isfile(str(voice)):
            voice_subdir, _ = path.split(voice)
            voice_dir = str(Path(voice_subdir).parent.absolute())
            voice_name = path.basename(path.normpath(voice_subdir))
            voices = [voice]
        elif path.isdir(str(voice)):
            voice_dir = str(Path(voice).parent.absolute())
            voice_name = path.basename(path.normpath(Path(voice).absolute()))
            voices = glob(path.join(voice, "*wav"))
        else:
            voices = None
            voice_dir = None
            voice_name = voice
        match model.lower():
            case 'xtts':
                model_parameters_extra = {
                    "model_name": "tts_models/multilingual/multi-dataset/xtts_v2"
                }
                generate_parameters_extra = {
                    'speaker_wav': voices,
                    'language': 'en'
                }
                if voices:
                    generate_parameters_extra['speaker_wav'] = voices
                elif voice_name:
                    generate_parameters_extra['speaker'] = voice_name
                else:
                    generate_parameters_extra['speaker'] = VOICE_XTTS
            case 'tortoise':
                model_parameters_extra = {
                    "model_name": "tts_models/en/multi-dataset/tortoise-v2",
                    **TORTOISE_ARGS
                }
                generate_parameters_extra = {
                    'preset': 'fast'
                }
                if voice_dir and voice_name:
                    generate_parameters_extra['voice_dir'] = voice_dir
                    generate_parameters_extra['speaker'] = voice_name
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
        self.log.write('TTS generation started with settings:\n'
                       f'model parameters: {model_parameters}\n'
                       f'generate parameters: {self.generate_parameters}\n'
                       f'target processor: {self.cpu}\n')
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
            result = stdout_buffer.getvalue()+"\n"+stderr_buffer.getvalue()
            if path.isfile(output_file):
                return result
            else:
                raise ValueError(result)
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(f'TTS conversion failed: {err}\n'
                           'You can try disabling gpu with --nogpu or gpu=0 in configuration.',
                           True)


if __name__ == "__main__":
    coqui = Coqui()
    print(coqui)
