"""main TTS processor"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from anyascii import anyascii
    from warnings import simplefilter
    import os
    import re
    from time import time
    import unicodedata
    import uuid
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# TTSPod modules
from logger import Logger
from util import check_engines

simplefilter(action='ignore', category=FutureWarning)

ENGINES = check_engines()


class Speech(object):
    """main TTS processor"""

    def __init__(self, config, dry=False, log=None):
        self.dry = dry
        if dry:
            return
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.config.nltk = False
        self.final_path = config.final_path
        # pylint: disable=import-outside-toplevel
        match self.config.engine.lower():
            case "openai" if "openai" in ENGINES:
                from paid import Paid
                self.tts = Paid(config=self.config, log=self.log)
            case "eleven" if "eleven" in ENGINES:
                from paid import Paid
                self.tts = Paid(config=self.config, log=self.log)
            case "whisper" if "whisper" in ENGINES:
                from whisper import Whisper
                self.tts = Whisper(config=self.config, log=self.log)
            case "coqui" if "coqui" in ENGINES:
                from coqui import Coqui
                self.tts = Coqui(config=self.config, log=self.log)
            case "f5" if "f5" in ENGINES:
                from f5 import F5
                self.tts = F5(config=self.config, log=self.log)
            case _:
                raise ValueError('TTS engine not configured')
        # pylint: enable=import-outside-toplevel
    def slugify(self, value):
        """convert an arbitrary string to a valid filename"""
        value = str(value)
        value = unicodedata.normalize('NFKD', value).encode(
            'ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value.lower())
        return re.sub(r'[-\s]+', '-', value).strip('-_')

    def speechify(self, title="No Title Available", raw_text="", overwrite=True):
        """workhorse TTS function"""
        clean_title = self.slugify(title)
        out_file = os.path.join(self.config.final_path, f'{clean_title}.mp3')
        if os.path.isfile(out_file) and not overwrite:
            self.log.write(f'skipping {out_file} because it already exists')
            return out_file
        text = anyascii(raw_text)
        text = re.sub('^.{,8}$', '', text, flags=re.MULTILINE)
        text = re.sub('^.{,8}$', '', text, flags=re.MULTILINE)
        text = re.sub('\n\n+', '\n\n', text, flags=re.MULTILINE)
        temp = str(uuid.uuid4())
        start_time = time()
        if os.path.exists(out_file):  # don't overwrite existing files
            out_file = os.path.join(
                self.config.final_path, f'{clean_title}-{temp}.mp3')

        if self.dry:  # quit if dry run
            self.log.write(f'dry run: not creating {out_file}')
            return
        self.log.write(f'starting TTS conversion to {out_file}')
        if title != "No Title Available":
            text = title.strip() + ".\n\n" + text.strip()
        self.log.write(self.tts.convert(text=text, output_file=out_file))
        elapsed = round(time() - start_time)
        self.log.write(
            f'TTS conversion of {out_file} complete, elapsed time: {elapsed} seconds')

        if os.path.isfile(out_file):
            os.chmod(out_file, 0o644)
            return out_file
        else:
            self.log.write(f'TTS conversion of {out_file} failed.')
            return None
