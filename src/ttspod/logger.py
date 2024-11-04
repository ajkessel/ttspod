"""general purpose logging"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from datetime import datetime
    from os import path
    from pathlib import Path
    from pprint import pprint
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()


class Logger(object):
    """screen and file logger"""

    def __init__(self, debug=False, quiet=False, logfile=None, maximum_level=0) -> None:
        self.debug = debug
        self.quiet = quiet
        self.log_path = logfile
        self.log_handle = None
        self.maximum_level = maximum_level
        if self.debug:
            print("Debug mode is on.")
        if self.maximum_level > 0:
            self.write(
                f'Logging set to level {self.maximum_level} out of 3.', error=False, log_level=1)
        if self.log_path:
            self.start()

    def start(self) -> None:
        """open or reopen log handle and print welcome message"""
        if self.log_handle:
            self.log_handle.close()
        try:
            if not path.isdir(path.dirname(self.log_path)):
                Path(path.dirname(self.log_path)).mkdir(
                    parents=True, exist_ok=True)
            self.log_handle = open(
                self.log_path, "a", buffering=1, encoding="utf-8")
            start_string = "TTSpod log file started at " + \
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"\n"
            line_block = (len(start_string)-1)*"-" + "\n"
            start_string = line_block + start_string + line_block
            self.log_handle.write(start_string)
        except Exception as err:  # pylint: disable=broad-except
            print(f"error opening logfile {self.log_path}: {err}")

    def write(self, text='', error=False, log_level=0) -> None:
        """write a message to screen and/or file"""
        if log_level > self.maximum_level and not self.debug:
            return
        if not text or not str(text):
            return
        if self.debug or (error and not self.quiet):
            print(text)
        text = str(text).replace('\n', '\n   ')  # indent multiline entries
        if self.log_handle:
            self.log_handle.write(datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S: ")+str(text)+"\n")

    def update(self, debug=None, quiet=None, logfile=None, maximum_level=0) -> None:
        """update logging with new settings"""
        new_debug = False
        self.maximum_level = maximum_level
        if debug is not None:
            if self.debug != debug:
                self.debug = debug
                new_debug = True
        if quiet is not None:
            self.quiet = quiet
        if logfile is not None:
            if self.log_handle:
                self.log_handle.close()
            self.log_path = logfile
        if self.log_path:
            self.start()
        if new_debug and debug:
            self.write('Debug mode is now on.')
        if self.maximum_level > 0:
            self.write(
                f'Logging set to level {self.maximum_level} out of 3.', error=False, log_level=1)

    def close(self) -> None:
        """close and release log"""
        if self.log_handle:
            self.log_handle.close()

if __name__ == '__main__':
    print("This is the TTSPod logger module. "
          "It is not intended to run separately except for debugging.")
    logger = Logger()
    pprint(vars(logger))
    pprint(dir(logger))
