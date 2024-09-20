from os import chmod, path, environ as e
from dotenv import load_dotenv
from pathlib import Path
try:
    from torch import cuda
except:
    pass

class Config(object):
    class Content(object):
        def __init__(self, debug = False):
            self.debug = debug
            return
    class Links(object):
        def __init__(self, debug = False):
            self.user_agent = e.get('ttspod_user_agent')
            self.debug = debug
            return
    class Wallabag(object):
        def __init__(self, debug = False):
            self.url = e.get('ttspod_wallabag_url')
            self.username = e.get('ttspod_wallabag_username')
            self.password = e.get('ttspod_wallabag_password')
            self.client_id = e.get('ttspod_wallabag_client_id')
            self.client_secret = e.get('ttspod_wallabag_client_secret')
            self.debug = debug
            return
    class Pocket(object):
        def __init__(self, debug = False):
            self.consumer_key = e.get('ttspod_pocket_consumer_key')
            self.access_token = e.get('ttspod_pocket_access_token')
            self.debug = debug
            return
    class Pod(object):
        def __init__(self, final_path = '', debug = False):
            self.url = path.join(e.get('ttspod_pod_url'),'')
            self.name = e.get('ttspod_pod_name','TTS podcast')
            self.author = e.get('ttspod_pod_author','TTS podcast author')
            self.image = e.get('ttspod_pod_image')
            if self.image and not 'http' in self.image:
                self.image = self.url + self.image
            self.description = e.get('ttspod_pod_description','TTS podcast description')
            self.language = e.get('ttspod_pod_language','en')
            self.ssh_server_path = e.get('ttspod_pod_ssh_server_path')
            if (self.ssh_server_path): self.ssh_server_path=path.join(self.ssh_server_path,'')
            self.ssh_server = e.get('ttspod_pod_ssh_server')
            self.final_path = final_path
            self.rss_file = path.join(final_path,"index.rss")
            self.debug = debug
    class Speech(object):
        def __init__(self, temp_path = '', final_path = '', debug = False):
            global openai_available
            global eleven_available
            global whisper_available
            try:
                openai_available
            except NameError: # for debugging purposes, where this module is run out of context
                openai_available = True
                eleven_available = True
                whisper_available = True
            self.engine = e.get('ttspod_engine','')
            self.eleven_api_key = e.get('ttspod_eleven_api_key')
            self.eleven_voice = e.get('ttspod_eleven_voice','Daniel')
            self.eleven_model = e.get('ttspod_eleven_model','eleven_monolingual_v1')
            self.openai_api_key = e.get('ttspod_openai_api_key')
            self.openai_voice = e.get('ttspod_openai_voice','onyx')
            self.openai_model = e.get('ttspod_openai_model','tts-1-hd')
            self.whisper_t2s_model = e.get('ttspod_whisper_t2s_model','whisperspeech/whisperspeech:t2s-fast-medium-en+pl+yt.model')
            self.whisper_s2a_model = e.get('ttspod_whisper_s2a_model','whisperspeech/whisperspeech:s2a-q4-hq-fast-en+pl.model')
            self.whisper_voice = e.get('ttspod_whisper_voice')
            self.temp_path = temp_path
            self.final_path = final_path
            self.debug = debug
            self.device = 'cpu'
            if self.engine in 'openai' and self.openai_api_key and openai_available:
                self.engine = 'openai'
            elif self.engine in 'eleven' and self.eleven_api_key and eleven_available:
                self.engine = 'eleven'
            elif self.engine in 'whisper' and whisper_available:
                self.engine = 'whisper'
                try:
                    if cuda.is_available():
                        self.device = 'cuda'
                except:
                    pass
            else:
                raise Exception("no valid TTS engine/API key found")
    def __init__(self,debug):
        load_dotenv()
        self.debug = e.get('ttspod_debug',debug)
        if self.debug: print(f'debug mode is on')
        self.max_length = int(e.get('ttspod_max_length',20000))
        self.max_articles = int(e.get('ttspod_max_articles',5))
        self.working_path = path.join(e.get('ttspod_working_path','./working'),'')
        self.temp_path = f'{self.working_path}temp/'
        self.final_path = f'{self.working_path}output/'
        self.pickle = f'{self.working_path}ttspod.pickle'
        self.pod = self.Pod(final_path = self.final_path, debug = self.debug)
        self.speech = self.Speech(temp_path = self.temp_path, final_path = self.final_path, debug = self.debug)
        self.content = self.Content(debug = self.debug)
        self.links = self.Links(debug = self.debug)
        self.wallabag = self.Wallabag(debug = self.debug)
        self.pocket = self.Pocket(debug = self.debug)
        Path(self.working_path).mkdir(parents=True, exist_ok=True)
        Path(self.temp_path).mkdir(parents=True, exist_ok=True)
        Path(self.final_path).mkdir(parents=True, exist_ok=True)
        chmod(self.final_path, 0o755)
        return
    def __str__(self):
        result = f'config: {str(vars(self))}\nwallabag: {str(vars(self.wallabag))}\npod {str(vars(self.pod))}\nspeech {str(vars(self.speech))}'
        return result
