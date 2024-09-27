# standard modules
try:
    from datetime import datetime
except Exception as e:
    print(f'Failed to import required module: {e}\nDo you need to run pip install -r requirements.txt?')
    exit()

class Logger(object):
    def __init__(self, debug = False, quiet = False, logfile = None):
        self.debug = debug
        self.quiet = quiet
        self.logfile = logfile
        self.loghandle = None
        if self.debug: print("debug mode is on")
        if self.logfile:
            try:
                self.loghandle = open(self.logfile, "a", buffering = 80)
                self.loghandle.write("ttspod logfile started at "+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"\n")
            except Exception as e:
                print("error opening logfile {self.logfile}: {e}")

    def write(self, text = '', error = False):
        if self.debug or (error and not self.quiet):
           print(text)
        if self.loghandle:
           self.loghandle.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S: ")+text+"\n")

    def update(self, debug = None, quiet = None, logfile = None):
        newdebug = False
        if debug is not None:
            if self.debug != debug:
                self.debug = debug
                newdebug = True
        if quiet is not None:
            self.quiet = quiet
        if logfile is not None:
            if self.loghandle: self.loghandle.close()
            self.logfile = logfile
        if self.logfile:
            try:
                self.loghandle = open(self.logfile, "a", buffering = 80)
                self.loghandle.write("ttspod logfile started at "+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"\n")
            except Exception as e:
                print("error opening logfile {self.logfile}: {e}")
        if newdebug and debug: self.write('debug mode is on')

    def close(self):
        if self.loghandle:
            self.loghandle.close()
