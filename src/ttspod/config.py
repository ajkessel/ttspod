"""digest and validate configuration files"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from dotenv import load_dotenv
    from importlib.resources import files
    from inspect import getsourcefile
    from os import chmod, path, environ as e, getcwd
    from pathlib import Path
    from posixpath import join as posix_join
    import re
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# TTSPod modules
from logger import Logger
from util import fix_path, check_engines

ENGINES = check_engines()


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

        def __init__(self, temp_path='./', final_path='./', engine=None,
                     max_workers=10, log=None, debug=False, gpu=1):
            self.log = log if log else Logger(debug=True)
            self.debug = debug
            self.gpu = gpu
            self.engine = engine if engine else e.get('ttspod_engine', '')
            self.engine = self.engine.lower()
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
            self.voice = e.get('ttspod_voice')
            if self.voice:
                self.voice = path.expanduser(self.voice)
            self.model = e.get(
                'ttspod_model', 'xtts')
            self.model = self.model.lower()
            if not self.voice or self.voice and not path.exists(self.voice):
                if self.engine == 'coqui' and self.model == 'xtts':
                    self.voice = 'Daisy Studious'
                else:
                    self.voice = files('ttspod').joinpath('data', 'sample.wav')
            self.language = e.get('ttspod_language')
            self.max_workers = max_workers
            self.temp_path = fix_path(temp_path, True)
            self.final_path = fix_path(final_path, True)
            if not self.engine:
                self.engine = 'coqui'
            # TODO: some more TTS engine validation
            self.log.write(
                f'Available TTS engines are: {ENGINES}.', log_level=3)
            self.log.write(
                f'TTS settings: engine {self.engine} / model {self.model} / voice {self.voice}',
                log_level=2
            )
            if not self.engine in ENGINES:
                self.log.write(f'TTS engine {self.engine} selected but not available.\n'
                               f'Available engines are: {ENGINES}\n'
                               'reinstall with quickstart.sh to add engines', True)
                self.engine = None

    def __init__(self, debug=True, engine=None, config_path=None, log=None, gpu=None, quiet=False):
        self.log = log if log else Logger(debug=debug)
        self.config_path = None
        if config_path and path.isfile(config_path):
            self.config_path = config_path
        elif (config_path and path.isdir(config_path) and
              path.isfile(path.join(config_path, '.env'))):
            self.config_path = path.join(config_path, '.env')
        elif path.isfile(path.join(Path.home(), '.config', 'ttspod.ini')):
            self.config_path = path.join(Path.home(), '.config', 'ttspod.ini')
        elif path.isfile(path.join(getcwd(), '.config', 'ttspod.ini')):
            self.config_path = path.join(getcwd(), '.config', 'ttspod.ini')
        elif path.isfile(path.join(getcwd(), '.env')):
            self.config_path = path.join(getcwd(), '.env')
        elif path.isfile(path.join(path.dirname(getsourcefile(lambda: 0)), '.env')):
            self.config_path = path.join(
                path.dirname(getsourcefile(lambda: 0)), '.env')
        elif path.isfile(path.join(path.dirname(path.realpath(__file__)), '.env')):
            self.config_path = path.join(
                path.dirname(path.realpath(__file__)), '.env')
        if self.config_path:
            if not quiet:
                self.log.write(
                    f'using stored configuration {self.config_path}', True)
            load_dotenv(self.config_path)
        if not any("ttspod" in x.lower() for x in list(e.keys())):
            raise ValueError(
                'No settings found. Create a .env file or specify the location with --config.'
            )
        if debug is None:
            self.debug = e.get('ttspod_debug', debug)
        else:
            self.debug = debug
        self.log_level = int(e.get('ttspod_log_level', 0))
        self.log.update(debug=self.debug, maximum_level=self.log_level)
        self.gpu = int(gpu if gpu is not None else e.get('ttspod_gpu', 1))
        self.max_length = int(e.get('ttspod_max_length', 20000))
        self.max_workers = int(e.get('ttspod_max_workers', 10))
        self.max_articles = int(e.get('ttspod_max_articles', 5))
        self.working_path = path.join(
            e.get('ttspod_working_path', './working'), '')
        if self.working_path:
            self.working_path = fix_path(self.working_path, True)
        if self.working_path.startswith('./'):
            self.working_path = re.sub(r'^./', '', self.working_path)
            self.working_path = path.join(
                path.dirname(__file__), self.working_path)
        self.temp_path = path.join(self.working_path, 'temp', '')
        self.final_path = path.join(self.working_path, 'output', '')
        self.log_path = e.get('ttspod_log')
        if self.log_path:
            self.log_path = fix_path(self.log_path, False)
        if self.log_path and not '/' in self.log_path and not '\\' in self.log_path:
            self.log_path = path.join(self.working_path, self.log_path)
        if self.log_path:
            self.log.update(debug=self.debug, logfile=self.log_path,
                            maximum_level=self.log_level)
        self.pickle_filename = 'ttspod.pickle'
        self.pickle = path.join(self.working_path, self.pickle_filename)
        if e.get('ttspod_state_file_path'):
            self.state_file_path = posix_join(
                e.get('ttspod_state_file_path'), '')+self.pickle_filename
        else:
            self.state_file_path = None
        if self.state_file_path:
            self.state_file_path = fix_path(self.state_file_path, False)
        self.speech = self.Speech(temp_path=self.temp_path, final_path=self.final_path,
                                  engine=engine, max_workers=self.max_workers, log=self.log,
                                  debug=self.debug, gpu=self.gpu)
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
        if ':' in str(self.state_file_path) or ':' in str(self.pod.ssh_server_path):
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
        if not path.isfile(path.join(self.working_path, 'no_image.lua')):
            with open(path.join(self.working_path, 'no_image.lua'), 'w', encoding='ascii') as f:
                f.write('function Image(el)\nreturn {}\n end')
        return True

    def __str__(self):
        result = (f'config: {str(vars(self))}\nwallabag: {str(vars(self.wallabag))}\n'
                  'pod {str(vars(self.pod))}\nspeech {str(vars(self.speech))}')
        return result
