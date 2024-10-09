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
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()


class Logger(object):
    """screen and file logger"""

    def __init__(self, debug=False, quiet=False, logfile=None):
        self.debug = debug
        self.quiet = quiet
        self.log_path = logfile
        self.log_handle = None
        if self.debug:
            print("debug mode is on")
        if self.log_path:
            try:
                self.log_handle = open(
                    self.log_path, "a", buffering=80, encoding="utf-8")
                self.log_handle.write(
                    "ttspod logfile started at "+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"\n")
            except Exception as err:  # pylint: disable=broad-except
                print(f"error opening logfile {self.log_path}: {err}")

    def write(self, text='', error=False):
        """write a message to screen and/or file"""
        if not text or not str(text):
            return
        if self.debug or (error and not self.quiet):
            print(text)
        text = str(text).replace('\n', '\n   ')  # indent multiline entries
        if self.log_handle:
            self.log_handle.write(datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S: ")+str(text)+"\n")

    def update(self, debug=None, quiet=None, logfile=None):
        """update logging with new settings"""
        new_debug = False
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
            try:
                self.log_handle = open(
                    self.log_path, "a", buffering=80, encoding="utf-8")
                self.log_handle.write(
                    "ttspod logfile started at "+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"\n")
            except Exception as err:  # pylint: disable=broad-except
                print(f"error opening logfile {self.log_path}: {err}")
        if new_debug and debug:
            self.write('debug mode is now on')

    def close(self):
        """close and release log"""
        if self.log_handle:
            self.log_handle.close()
