"""main application module, typically invoked from ttspod"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from argparse import ArgumentParser
    from os import isatty, path, getcwd
    from sys import stdin, stdout, exc_info
    from validators import url
    from traceback import format_exc
    from pathlib import Path
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# ttspod modules
from .version import __version__
from .util import get_character, get_lock, release_lock, upgrade


class App(object):
    """ttspod application"""

    def __init__(self):
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
        self.gpu = None
        self.upgrade = False
        self.wallabag = None
        self.pocket = None
        self.insta = None
        self.url = None

    def parse(self):
        """parse command-line arguments"""
        parser = ArgumentParser(
            description='Convert any content to a podcast feed.')
        parser.add_argument('url', nargs='*', action='store', type=str, default="",
                            help="specify any number of URLs or local documents "
                            "(plain text, HTML, PDF, Word documents, etc) "
                            "to add to your podcast feed")
        parser.add_argument("-c", "--config", nargs='?', const='AUTO', default=None,
                            help="specify path for config file "
                            "(default ~/.config/ttspod.ini if it exists, "
                            "otherwise .env in the current directory)"
                            )
        parser.add_argument("-g", "--generate", nargs='?', const='AUTO', default=None,
                            help="generate a new config file"
                            "(default ~/.config/ttspod.ini if ~/.config exists, "
                            "otherwise .env in the current directory)"
                            )
        parser.add_argument("-w", "--wallabag", nargs='?', const='audio', default=None,
                            help="add unprocessed items with specified tag (default audio) "
                            "from your wallabag feed to your podcast feed")
        parser.add_argument("-i", "--insta", nargs='?', const='audio', default=None,
                            help="add unprocessed items with specified tag (default audio) "
                            "from your instapaper feed to your podcast feed, "
                            "or use tag ALL for default inbox")
        parser.add_argument("-p", "--pocket", nargs='?', const='audio', default=None,
                            help="add unprocessed items with specified tag (default audio) "
                            "from your pocket feed to your podcast feed")
        parser.add_argument("-l", "--log", nargs='?', const='ttspod.log',
                            default=None, help="log all output to specified filename "
                            "(default ttspod.log)")
        parser.add_argument("-q", "--quiet", nargs='?', default=None,
                            help="no visible output (all output will go to log if specified)")
        parser.add_argument(
            "-d", "--debug", action='store_true', help="include debug output")
        parser.add_argument("-r", "--restart", action='store_true',
                            help="wipe state file clean and start new podcast feed")
        parser.add_argument("-f", "--force", action='store_true',
                            help="force addition of podcast even if "
                            "cache indicates it has already been added")
        parser.add_argument("-t", "--title", action='store',
                            help="specify title for content provided via pipe")
        parser.add_argument("-e", "--engine", action='store',
                            help="specify TTS engine for this session "
                            "(whisper, coqui, openai, eleven)")
        parser.add_argument("-s", "--sync", action='store_true',
                            help="sync podcast episodes and state file")
        parser.add_argument("-n", "--dry-run", action='store_true',
                            help="do not actually create or sync audio files")
        parser.add_argument("--nogpu", action='store_true',
                            help="disable GPU support (may be necessary for Mac)")
        parser.add_argument("-u", "--upgrade", action='store_true',
                            help="upgrade to latest version")
        parser.add_argument("-v", "--version", action='store_true',
                            help="print version number")
        args = parser.parse_args()
        self.generate = args.generate
        if self.generate:
            if self.generate == "AUTO":
                self.generate_env_file(None)
            else:
                self.generate_env_file(self.generate)
            return False
        if args.version:
            print(__version__)
            return False
        self.config_path = args.config
        self.debug = args.debug
        self.quiet = args.quiet
        if not self.quiet:
            print(f'TTSPod v{__version__}')
        if self.quiet:
            self.debug = False
        self.log = args.log
        self.dry = args.dry_run
        self.gpu = 0 if args.nogpu else None
        self.force = args.force
        self.clean = args.restart
        self.title = args.title if hasattr(args, 'title') else None
        self.engine = args.engine if hasattr(
            args, 'engine') else None
        self.got_pipe = not isatty(stdin.fileno())
        self.wallabag = args.wallabag
        self.pocket = args.pocket
        self.insta = args.insta
        self.url = args.url
        if args.upgrade:
            upgrade(force = self.force, debug=self.debug)
            return False
        if not (
            args.url or
            args.wallabag or
            args.pocket or
            args.sync or
            self.got_pipe or
            args.insta
        ):
            parser.print_help()
            return False
        return True

    def generate_env_file(self, env_file):
        """generate a new .env file"""
        if not env_file:
            if path.isdir(path.join(Path.home(), '.config')):
                env_file = path.join(Path.home(), '.config', 'ttspod.ini')
            else:
                env_file = path.join(getcwd(), '.env')
        if path.isdir(env_file):
            env_file = path.join(env_file, '.env')
        if path.isfile(env_file):
            check = False
            while not check:
                stdout.write(
                    f'{env_file} already exists. Do you want to overwrite? (y/n) ')
                stdout.flush()
                check = get_character()
                if not (check == 'y' or check == 'n'):
                    check = False
                elif check == 'n':
                    stdout.write('exiting...\n')
                    exit()
        with open(env_file, 'w', encoding='utf-8') as f:
            # cspell: disable
            f.write('''
# global parameters
# debug - set to anything for verbose output, otherwise leave blank
ttspod_debug=""
# gpu - set to 0 to disable GPU, otherwise will attempt to use GPU
# ttspod_gpu="0"
# log - filename (and optional path) for logging output
# Leave empty for no logging
# If no path is specified, logfile is put under ttspod_working_path
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
# state_file_path: optional remote location to store state file
# if the path includes a domain name the file will be synced to and from that location on each run
# this allows you to have multiple instances of this script running on different boxes without duplicate blog entries
# ttspod_state_file_path="adam@example.com:ttspod/working"
ttspod_state_file_path=""

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
# ttspod_pod_server_path="adam@example.com:public_html/my_podcast"
# if you leave this empty, the podcast RSS file and mp3 files will remain in your working_path folder
ttspod_pod_server_path=""

# TTS API keys and other parameters
# Eleven and OpenAI require a paid API key; coqui and whisper  can run on your device (if it is powerful enough) for free
ttspod_engine="coqui" # should be openai / eleven / coqui / whisper
ttspod_model="xtts" # for coqui, should be xtts or tortoise

# voice selection

# for tortoise, one of the following names, or a path to a folder with WAV files for cloning
# angie applejack cond_latent_example daniel deniro emma freeman geralt halle jlaw lj mol
# myself pat pat2 rainbow snakes tim_reynolds tom train_atkins train_daws train_dotrice train_dreams
# train_empire train_grace train_kennard train_lescault train_mouse weaver william

# for xtts, one of the following names, or a path to a folder with WAV files for cloning
# 'Claribel Dervla' 'Daisy Studious' 'Gracie Wise' 'Tammie Ema' 'Alison Dietlinde'
# 'Ana Florence' 'Annmarie Nele' 'Asya Anara' 'Brenda Stern' 'Gitta Nikolina'
# 'Henriette Usha' 'Sofia Hellen' 'Tammy Grit' 'Tanja Adelina'
# 'Vjollca Johnnie' 'Andrew Chipper' 'Badr Odhiambo' 'Dionisio Schuyler'
# 'Royston Min' 'Viktor Eka' 'Abrahan Mack' 'Adde Michal' 'Baldur Sanjin' 
# 'Craig Gutsy' 'Damien Black' 'Gilberto Mathias' 'Ilkin Urbano' 'Kazuhiko Atallah'
# 'Ludvig Milivoj' 'Suad Qasim' 'Torcull Diarmuid' 'Viktor Menelaos' 
# 'Zacharie Aimilios' 'Nova Hogarth' 'Maja Ruoho' 'Uta Obando' 'Lidiya Szekeres' 
# 'Chandra MacFarland' 'Szofi Granger' 'Camilla Holmström' 'Lilya Stainthorpe' 
# 'Zofija Kendrick' 'Narelle Moon' 'Barbora MacLean' 'Alexandra Hisakawa' 'Alma María'
# 'Rosemary Okafor' 'Ige Behringer' 'Filip Traverse' 'Damjan Chapman' 
# 'Wulf Carlevaro' 'Aaron Dreschner' 'Kumar Dahl' 'Eugenio Mataracı' 'Ferran Simen'
# 'Xavier Hayasaka' 'Luis Moray' 'Marcos Rudaski'

ttspod_voice='Daisy Studious'

# sample models to use with whisper; I haven't done a lot of research here, but these seem to work okay
# list of models available at https://huggingface.co/WhisperSpeech/WhisperSpeech/tree/main
ttspod_whisper_t2s_model="whisperspeech/whisperspeech:t2s-fast-medium-en+pl+yt.model"
ttspod_whisper_s2a_model="whisperspeech/whisperspeech:s2a-q4-hq-fast-en+pl.model"

# API keys and settings for paid TTS services
ttspod_eleven_api_key=""
ttspod_eleven_voice="Daniel"
ttspod_eleven_model="eleven_monolingual_v1"
ttspod_openai_api_key=""
ttspod_openai_voice="onyx"
ttspod_openai_model="tts-1-hd"
''')
# cspell: enable
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
            # this import is slow (loads TTS engines), so only import when needed
            # there is probably a better way to do this by refactoring
            from .main import Main  # pylint: disable=import-outside-toplevel
            self.main = Main(
                debug=self.debug,
                config_path=self.config_path,
                engine=self.engine,
                force=self.force,
                dry=self.dry,
                clean=self.clean,
                logfile=self.log,
                gpu=self.gpu,
                quiet=self.quiet
            )
            if self.got_pipe:
                pipe_input = str(stdin.read())
                if pipe_input:
                    self.main.process_content(pipe_input, self.title)
            if self.wallabag:
                self.main.process_wallabag(self.wallabag)
            if self.pocket:
                self.main.process_pocket(self.pocket)
            if self.insta:
                self.main.process_insta(self.insta)
            for i in self.url:
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
        # only import remaining modules if we have something to do
        app.run()     # run the main workflow


if __name__ == "__main__":
    main()
