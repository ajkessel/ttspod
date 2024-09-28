"""main application module, typically invoked from ttspod"""

# standard modules
try:
    from argparse import ArgumentParser
    from os import isatty, path
    from sys import stdin, exc_info
    from validators import url
    from traceback import format_exc
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# TTSPod modules
from main import Main
from util import getLock, release_lock


class App(object):
    """ttspod application"""

    def __init__(self):
        self.args = None
        self.debug = None
        self.quiet = None
        self.log = None
        self.dry = None
        self.force = None
        self.clean = None
        self.title = None
        self.engine = None
        self.got_pipe = None
        self.main = None

    def parse(self):
        """parse command-line arguments"""
        parser = ArgumentParser(
            description='Convert any content to a podcast feed.')
        parser.add_argument('url', nargs='*', action='store', type=str, default="",
                            help="specify any number of URLs or local documents "
                            "(plain text, HTML, PDF, Word documents, etc) "
                            "to add to your podcast feed")
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
        parser.add_argument("-c", "--clean", action='store_true',
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
        self.args = parser.parse_args()
        self.debug = self.args.debug
        self.quiet = self.args.quiet
        if self.quiet:
            self.debug = False
        self.log = self.args.log
        self.dry = self.args.dry_run
        self.force = self.args.force
        self.clean = self.args.clean
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

    def run(self):
        """primary app loop"""
        try:
            if not getLock():
                if not self.force:
                    print(
                        'Another instance of ttspod was detected running. '
                        'Execute with -f or --force to force execution.')
                    return False
                else:
                    release_lock()
            self.main = Main(
                debug=self.debug,
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
