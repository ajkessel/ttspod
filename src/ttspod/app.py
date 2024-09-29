"""main application module, typically invoked from ttspod"""

# standard modules
try:
    from argparse import ArgumentParser
    from os import isatty, path, getcwd
    from sys import stdin, stdout, exc_info
    from validators import url
    from traceback import format_exc
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# TTSPod modules
from .main import Main
from .util import get_lock, release_lock
from .version import __version__
from .util import get_character

class App(object):
    """ttspod application"""

    def __init__(self):
        self.args = None
        self.clean = None
        self.config_path = None
        self.debug = None
        self.dry = None
        self.engine = None
        self.force = None
        self.generate = None
        self.got_pipe = None
        self.log = None
        self.main = None
        self.quiet = None
        self.title = None

    def parse(self):
        """parse command-line arguments"""
        parser = ArgumentParser(
            description='Convert any content to a podcast feed.')
        parser.add_argument('url', nargs='*', action='store', type=str, default="",
                            help="specify any number of URLs or local documents "
                            "(plain text, HTML, PDF, Word documents, etc) "
                            "to add to your podcast feed")
        parser.add_argument("-c", "--config", nargs='?', const='.env', default="",
                            help="specify path for config file (default .env in current directory")
        parser.add_argument("-g", "--generate", nargs='?', const='.env', default="",
                            help="generate a new config file (default .env in current directory)")
        parser.add_argument("-w", "--wallabag", nargs='?', const='audio', default="",
                            help="add unprocessed items with specified tag (default audio) "
                            "from your wallabag feed to your podcast feed")
        parser.add_argument("-i", "--insta", nargs='?', const='audio', default="",
                            help="add unprocessed items with specified tag (default audio) "
                            "from your instapaper feed to your podcast feed, "
                            "or use tag ALL for default inbox")
        parser.add_argument("-p", "--pocket", nargs='?', const='audio', default="",
                            help="add unprocessed items with specified tag (default audio) "
                            "from your pocket feed to your podcast feed")
        parser.add_argument("-l", "--log", nargs='?',
                            default="", help="log all output to specified filename")
        parser.add_argument("-q", "--quiet", nargs='?', default="",
                            help="no visible output (all output will go to log if specified)")
        parser.add_argument(
            "-d", "--debug", action='store_true', help="include debug output")
        parser.add_argument("-r", "--restart", action='store_true',
                            help="wipe cache clean and start new podcast feed")
        parser.add_argument("-f", "--force", action='store_true',
                            help="force addition of podcast even if "
                            "cache indicates it has already been added")
        parser.add_argument("-t", "--title", action='store',
                            help="specify title for content provided via pipe")
        parser.add_argument("-e", "--engine", action='store',
                            help="specify TTS engine for this session "
                            "(whisper, coqui, openai, eleven)")
        parser.add_argument("-s", "--sync", action='store_true',
                            help="sync podcast episodes and cache file")
        parser.add_argument("-n", "--dry-run", action='store_true',
                            help="dry run: do not actually create or sync audio files")
        parser.add_argument("-v", "--version", action='store_true',
                            help="print version number")
        self.args = parser.parse_args()
        self.generate = self.args.generate
        if self.generate:
            self.generate_env_file(self.generate)
        if self.args.version:
            print(__version__)
            exit()
        self.config_path = self.args.config
        self.debug = self.args.debug
        self.quiet = self.args.quiet
        if self.quiet:
            self.debug = False
        self.log = self.args.log
        self.dry = self.args.dry_run
        self.force = self.args.force
        self.clean = self.args.restart
        self.title = self.args.title if hasattr(self.args, 'title') else None
        self.engine = self.args.engine if hasattr(
            self.args, 'engine') else None
        self.got_pipe = not isatty(stdin.fileno())
        if not (
            self.args.url or
            self.args.wallabag or
            self.args.pocket or
            self.args.sync or
            self.got_pipe or
            self.args.insta
        ):
            parser.print_help()
            return False
        return True

    def generate_env_file(self, env_file):
        """generate a new .env file"""
        if not env_file:
            env_file=path.join(getcwd(),'.env')
        if path.isdir(env_file):
            env_file=path.join(env_file,'.env')
        if path.isfile(env_file):
            check = False
            while not check:
                stdout.write(f'{env_file} already exists. Do you want to overwrite? (y/n) ')
                stdout.flush()
                check = get_character()
                if not (check == 'y' or check =='n'):
                    check = False
                elif check == 'n':
                    stdout.write('exiting...\n')
                    exit()
        with open(env_file,'w',encoding='utf-8') as f:
            f.write('''
# global parameters
# debug - set to anything for verbose output, otherwise leave blank
ttspod_debug=""
# log - filename for logging output, leave blank for no logging
# if not path is specified, logfile would be put under working path
ttspod_log=""
# path for temporary files (defaults to ./working)
ttspod_working_path="./working"
# include attachments to emails
ttspod_attachments=1
# max_length: skip articles longer than this number of characters (default 20000)
# you likely want to set some cap if you are using a paid TTS service (OpenAI or Eleven)
ttspod_max_length=20000
# max_workers: how many parallel threads to execute when performing OpenAI/Eleven TTS (default 10)
ttspod_max_workers=10
# max_articles: max number of articles to retrieve with each execution (default 5)
# you likely want to set some cap if you are using a paid TTS service (OpenAI or Eleven)
ttspod_max_articles=5
# user_agent: optional user-agent configuration
# you may need this to avoid being blocked as a "python requests" requestor
#ttspod_user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
ttspod_user_agent=""
# cache_path: optional remote location to store cache file
# if the path includes a domain name the file will be synced to and from that location on each run
# this allows you to have multiple instances of this script running on different boxes without duplicate blog entries
# ttspod_cache_path="adam@example.com:ttspod/working"
ttspod_cache_path=""

# ssh settings - you"ll need to configure this to sync your podcast to a server
# specify either a password or an ssh keyfile (e.g. ~/.ssh/id_rsa)
# if you leave this empty but have a remote podcast server, we will try our best to find your username and local keyfile automatically
ttspod_ssh_keyfile=""
ttspod_ssh_password=""

# wallabag parameters - you need to define these for anything to work
# create a client at https://your.wallabag.url/developer/client/create
# then populate with the information below
ttspod_wallabag_url=""
ttspod_wallabag_username=""
ttspod_wallabag_password=""
ttspod_wallabag_client_id=""
ttspod_wallabag_client_secret=""

# pocket parameters 
# create a consumer key at https://getpocket.com/developer/
# get access token from https://reader.fxneumann.de/plugins/oneclickpocket/auth.php
ttspod_pocket_consumer_key=""
ttspod_pocket_access_token=""

# Instapaper parameters
# request a consumer key at https://www.instapaper.com/main/request_oauth_consumer_token
ttspod_insta_username=""
ttspod_insta_password=""
ttspod_insta_key=""
ttspod_insta_secret=""


# podcast settings
# pod_url: Root URL for podcast rss file (index.rss) and generated MP3 files
ttspod_pod_url=""
ttspod_pod_name="A Custom TTS Feed"
ttspod_pod_description="A podcast description"
ttspod_pod_author="John Smith"
ttspod_pod_image="icon.png"
ttspod_pod_language="en"
# pod_server_path: real server and path corresponding to the above URL
# format is username@domainname.com:/path/to/folder
# for example
# ttspod_pod_path="adam@example.com:public_html/my_podcast"
# if you leave this empty, the podcast RSS file and mp3 files will remain in your working_path folder
ttspod_pod_server_path=""

# TTS API keys and other parameters
# Eleven and OpenAI require a paid API key; whisper or coqui can run on your device (if it is powerful enough) for free
# if only one engine is defined, that will be used; otherwise specify engine on next line
ttspod_engine="whisper" # should be openai / eleven / whisper / coqui
# sample models to use with whisper; I haven't done a lot of research here, but these seem to work okay
# list of models available at https://huggingface.co/WhisperSpeech/WhisperSpeech/tree/main
ttspod_whisper_t2s_model="whisperspeech/whisperspeech:t2s-fast-medium-en+pl+yt.model"
ttspod_whisper_s2a_model="whisperspeech/whisperspeech:s2a-q4-hq-fast-en+pl.model"
# whisper_voice: path to a sound file of a ~30 second voice sound clip to use as model for speech generation
ttspod_whisper_voice=""
ttspod_coqui_model="tts_models/en/ljspeech/tacotron2-DDC"
# if you select a multi-speaker or multi-language coqui model, you will need to fill in values below
ttspod_coqui_speaker=""
ttspod_coqui_language=""
ttspod_eleven_api_key=""
ttspod_eleven_voice="Daniel"
ttspod_eleven_model="eleven_monolingual_v1"
ttspod_openai_api_key=""
ttspod_openai_voice="onyx"
ttspod_openai_model="tts-1-hd"
# remove this line to get verbose TTS console output from Whisper
TORCH_LOGS="-all"
# specify directory for huggingface cache files
#HF_HOME=""
''')
        print(f'{env_file} written. Now edit to run ttspod.')
        exit()

    def run(self):
        """primary app loop"""
        try:
            if not get_lock():
                if not self.force:
                    print(
                        'Another instance of ttspod was detected running. '
                        'Execute with -f or --force to force execution.')
                    return False
                else:
                    release_lock()
            self.main = Main(
                debug=self.debug,
                config_path=self.config_path,
                engine=self.engine,
                force=self.force,
                dry=self.dry,
                clean=self.clean,
                logfile=self.log,
                quiet=self.quiet
            )
            if self.got_pipe:
                pipe_input = str(stdin.read())
                if pipe_input:
                    self.main.process_content(pipe_input, self.title)
            if self.args.wallabag:
                self.main.process_wallabag(self.args.wallabag)
            if self.args.pocket:
                self.main.process_pocket(self.args.pocket)
            if self.args.insta:
                self.main.process_insta(self.args.insta)
            for i in self.args.url:
                if url(i):
                    self.main.process_link(i, self.title)
                elif path.isfile(i):
                    self.main.process_file(i, self.title)
                else:
                    print(f'command-line argument {i} not recognized')
            return self.main.finalize()
        # pylint: disable=W0718
        # global exception catcher for application loop
        except Exception:
            exc_type, _, exc_tb = exc_info()
            fname = path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print('Error occurred:\n', exc_type, fname, exc_tb.tb_lineno)
            if self.debug:
                print('-----Full Traceback-----\n', format_exc())
        # pylint: enable=W0718

        finally:
            release_lock()


def main():
    """nominal main loop to read arguments and execute app"""
    app = App()
    if app.parse():   # parse command-line arguments
        app.run()     # run the main workflow


if __name__ == "__main__":
    main()
