"""main application module, typically invoked from ttspod CLI"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from argparse import ArgumentParser
    from importlib.resources import files
    from os import isatty, path, getcwd
    from pathlib import Path
    from shutil import copy
    from sys import stdin, stdout, exc_info
    from traceback import format_exc
    from validators import url
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# ttspod modules
from version import __version__
from util import get_character, get_lock, release_lock, upgrade


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
            upgrade(force=self.force, debug=self.debug)
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
                if isinstance(check, bytes):
                    check = check.decode()
                if not (check == 'y' or check == 'n'):
                    check = False
                elif check == 'n':
                    stdout.write('exiting...\n')
                    exit()
        try:
            copy(files('ttspod').joinpath('data', 'dotenv.env'), env_file)
            print(f'{env_file} written. Now edit to run ttspod.')
        except Exception as err:  # pylint: disable=broad-except
            print(f'Error creating {env_file}: {err}\n.')
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
            from main import Main  # pylint: disable=import-outside-toplevel
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
