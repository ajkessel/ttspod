"""digest and validate configuration files"""
# standard modules
try:
    from os import chmod, path, environ as e, getcwd
    from dotenv import load_dotenv
    from inspect import getsourcefile
    from pathlib import Path
    from posixpath import join as posix_join
    from warnings import filterwarnings
    import re
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# TTSPod modules
from .logger import Logger

# optional modules - disable linting since we are checking if modules exist
# pylint: disable=unused-import
CPU = 'cpu'
try:
    from torch import cuda
    if cuda.is_available():
        CPU = 'cuda'
except ImportError:
    pass
try:
    from torch.backends import mps
    if mps.is_available():
        CPU = 'mps'
except ImportError:
    pass
ENGINES = {}
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import save
    ENGINES['eleven'] = True
except ImportError:
    pass
try:
    from whisperspeech.pipeline import Pipeline
    import torch
    import torchaudio
    filterwarnings("ignore")  # to suppress TTS output
    ENGINES['whisper'] = True
except ImportError:
    pass
try:
    from TTS.api import TTS
    ENGINES['coqui'] = True
except ImportError:
    pass
try:
    from openai import OpenAI
    # necessary for OpenAI TTS streaming
    filterwarnings("ignore", category=DeprecationWarning)
    ENGINES['openai'] = True
except ImportError:
    pass
# pylint: enable=unused-import


class Config(object):
    """configuration settings"""
    class Content(object):
        """content processor settings"""

        def __init__(self, working_path=None, log=None):
            self.log = log if log else Logger(debug=True)
            self.attachment_path = path.join(working_path, "attachments")
            self.lua_path = working_path
            self.attachments = e.get('ttspod_attachments')
            if self.attachments and self.attachment_path:
                Path(self.attachment_path).mkdir(parents=True, exist_ok=True)
            return

    class Links(object):
        """link processor settings"""

        def __init__(self, log=None):
            self.log = log if log else Logger(debug=True)
            self.user_agent = e.get('ttspod_user_agent')

    class Wallabag(object):
        """wallabag input settings"""

        def __init__(self, log=None):
            self.log = log if log else Logger(debug=True)
            self.url = e.get('ttspod_wallabag_url')
            self.username = e.get('ttspod_wallabag_username')
            self.password = e.get('ttspod_wallabag_password')
            self.client_id = e.get('ttspod_wallabag_client_id')
            self.client_secret = e.get('ttspod_wallabag_client_secret')

    class Pocket(object):
        """pocket input settings"""

        def __init__(self, log=None):
            self.log = log if log else Logger(debug=True)
            self.consumer_key = e.get('ttspod_pocket_consumer_key')
            self.access_token = e.get('ttspod_pocket_access_token')

    class Insta(object):
        """instapaper input settings"""

        def __init__(self, log=None):
            self.log = log if log else Logger(debug=True)
            self.key = e.get('ttspod_insta_key')
            self.secret = e.get('ttspod_insta_secret')
            self.username = e.get('ttspod_insta_username')
            self.password = e.get('ttspod_insta_password')

    class Pod(object):
        """podcast output settings"""

        def __init__(self, final_path='', ssh_keyfile=None, ssh_password=None, log=None):
            self.log = log if log else Logger(debug=True)
            self.url = posix_join(e.get('ttspod_pod_url'), '')
            self.name = e.get('ttspod_pod_name', 'TTS podcast')
            self.author = e.get('ttspod_pod_author', 'TTS podcast author')
            self.image = e.get('ttspod_pod_image')
            if self.image and not 'http' in self.image:
                self.image = self.url + self.image
            self.description = e.get(
                'ttspod_pod_description', 'TTS podcast description')
            self.language = e.get('ttspod_pod_language', 'en')
            self.ssh_server_path = e.get('ttspod_pod_server_path')
            self.ssh_keyfile = ssh_keyfile
            self.ssh_password = ssh_password
            self.final_path = final_path
            self.rss_file = path.join(final_path, 'index.rss')

    class Speech(object):
        """tts processor settings"""

        def __init__(self, temp_path='', final_path='', engine=None, max_workers=10, log=None):
            self.log = log if log else Logger(debug=True)
            self.engine = engine if engine else e.get('ttspod_engine', '')
            self.eleven_api_key = e.get('ttspod_eleven_api_key')
            self.eleven_voice = e.get('ttspod_eleven_voice', 'Daniel')
            self.eleven_model = e.get(
                'ttspod_eleven_model', 'eleven_monolingual_v1')
            self.openai_api_key = e.get('ttspod_openai_api_key')
            self.openai_voice = e.get('ttspod_openai_voice', 'onyx')
            self.openai_model = e.get('ttspod_openai_model', 'tts-1-hd')
            self.whisper_t2s_model = e.get(
                'ttspod_whisper_t2s_model',
                'whisperspeech/whisperspeech:t2s-fast-medium-en+pl+yt.model')
            self.whisper_s2a_model = e.get(
                'ttspod_whisper_s2a_model',
                'whisperspeech/whisperspeech:s2a-q4-hq-fast-en+pl.model')
            self.whisper_voice = e.get('ttspod_whisper_voice')
            self.coqui_model = e.get(
                'ttspod_coqui_model', 'tts_models/en/ljspeech/tacotron2-DDC')
            self.coqui_speaker = e.get('ttspod_coqui_speaker')
            self.coqui_language = e.get('ttspod_coqui_language')
            self.max_workers = max_workers
            self.temp_path = temp_path
            self.final_path = final_path
            if not self.engine:
                self.engine = 'whisper'
            # FIXME: some more TTS engine validation
            if not self.engine in ENGINES:
                raise ValueError("no valid TTS engine/API key found")
            self.device = CPU
            self.log.write(f'using {self.device} for local TTS processing')

    def __init__(self, debug=None, engine=None, config_path=None, log=None):
        self.log = log if log else Logger(debug=True)
        if config_path:
            if path.isfile(config_path):
                self.config_path = config_path
            elif path.isdir(config_path) and path.isfile(path.join(config_path,'.env')):
                self.config_path = path.join(config_path,'.env')
            elif path.isfile(path.join(getcwd(),'.env')):
                self.config_path = path.join(getcwd(),'.env')
            elif path.isfile(path.join(path.dirname(getsourcefile(lambda:0)),'.env')):
                self.config_path = path.join(path.dirname(getsourcefile(lambda:0)),'.env')
            elif path.isfile(path.join(path.dirname(path.realpath(__file__)),'.env')):
                self.config_path = path.join(path.dirname(path.realpath(__file__)),'.env')
        if self.config_path:
            load_dotenv(self.config_path)
        if not any("ttspod" in x for x in list(e.keys())):
            raise ValueError(
                'No settings found. Create a .env file or specify the location with --config.'
                )
        if debug is None:
            self.debug = e.get('ttspod_debug', debug)
        else:
            self.debug = debug
        self.log.update(debug=self.debug)
        self.max_length = int(e.get('ttspod_max_length', 20000))
        self.max_workers = int(e.get('ttspod_max_workers', 10))
        self.max_articles = int(e.get('ttspod_max_articles', 5))
        self.working_path = path.join(
            e.get('ttspod_working_path', './working'), '')
        if self.working_path:
            self.working_path = re.sub(
                r'~/', str(Path.home()).replace('\\', '/') + '/', self.working_path)
        if self.working_path.startswith('./'):
            self.working_path = re.sub(r'^./', '', self.working_path)
            self.working_path = path.join(
                path.dirname(__file__), self.working_path)
        self.temp_path = path.join(self.working_path, 'temp', '')
        self.final_path = path.join(self.working_path, 'output', '')
        self.log_path = e.get('ttspod_log')
        if self.log_path:
            self.log_path = re.sub(
                r'~/', str(Path.home()).replace('\\', '/') + '/',
                self.log_path
                )
        if self.log_path and not '/' in self.log_path and not '\\' in self.log_path:
            self.log_path = path.join(self.working_path, self.log_path)
        if self.log_path:
            self.log.update(logfile=self.log_path)
        self.pickle_filename = 'ttspod.pickle'
        self.pickle = path.join(self.working_path, self.pickle_filename)
        if e.get('ttspod_cache_path'):
            self.cache_path = posix_join(
                e.get('ttspod_cache_path'), '')+self.pickle_filename
        else:
            self.cache_path = None
        if self.cache_path:
            self.cache_path = re.sub(
                r'~/', str(Path.home()).replace('\\', '/') + '/', self.cache_path)
        self.speech = self.Speech(temp_path=self.temp_path, final_path=self.final_path,
                                  engine=engine, max_workers=self.max_workers, log=self.log)
        self.content = self.Content(
            working_path=self.working_path, log=self.log)
        self.links = self.Links(log=self.log)
        self.wallabag = self.Wallabag(log=self.log)
        self.pocket = self.Pocket(log=self.log)
        self.insta = self.Insta(log=self.log)
        self.ssh_keyfile = e.get('ttspod_ssh_keyfile')
        self.ssh_password = e.get('ttspod_ssh_password')
        if self.ssh_keyfile:
            self.ssh_keyfile = re.sub(
                r'~/', str(Path.home()).replace('\\', '/') + '/', self.ssh_keyfile)
        if not (self.ssh_keyfile or self.ssh_password):
            key_list = ['id_rsa', 'id_ecdsa', 'id_ecdsa_sk',
                        'id_ed25519', 'id_ed25519_sk', 'id_dsa']
            for key in key_list:
                keyfile = path.join(Path.home(), '.ssh',
                                    key).replace('\\', '/')
                if path.isfile(keyfile):
                    self.ssh_keyfile = keyfile
                    break
        self.pod = self.Pod(
            final_path=self.final_path,
            ssh_keyfile=self.ssh_keyfile,
            ssh_password=self.ssh_password,
            log=self.log
        )
        self.make_files()
        self.validate()

    def validate(self):
        """validate settings and throw error if necessary"""
        if ':' in str(self.cache_path) or ':' in str(self.pod.ssh_server_path):
            if not self.ssh_keyfile or self.ssh_password:
                raise ValueError(
                    "Remote paths configured for syncing but no SSH keyfile or password provided."
                )
        if self.ssh_keyfile and not path.isfile(self.ssh_keyfile) and not self.ssh_password:
            raise ValueError(
                f"ssh_keyfile {self.ssh_keyfile} does not exist or is not readable."
            )
        if not (
            path.isdir(str(self.working_path)) and
            path.isdir(self.temp_path) and
            path.isdir(self.final_path)
        ):
            raise ValueError(
                f"Unable to access working path {self.working_path}."
            )

    def make_files(self):
        """create working files and directories"""
        Path(self.working_path).mkdir(parents=True, exist_ok=True)
        Path(self.temp_path).mkdir(parents=True, exist_ok=True)
        Path(self.final_path).mkdir(parents=True, exist_ok=True)
        chmod(self.final_path, 0o755)
        if not path.isfile(path.join(self.working_path,'no_image.lua')):
            with open(path.join(self.working_path,'no_image.lua'), 'w', encoding='ascii') as f:
                f.write('function Image(el)\nreturn {}\n end')
        return True

    def __str__(self):
        result = (f'config: {str(vars(self))}\nwallabag: {str(vars(self.wallabag))}\n'
                  'pod {str(vars(self.pod))}\nspeech {str(vars(self.speech))}')
        return result