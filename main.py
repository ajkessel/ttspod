# standard modules
try:
    from os import path
    from shutil import move
    import datetime
    import pickle
except Exception as e:
    print(f'Failed to import required module: {e}\nDo you need to run pip install -r requirements.txt?')
    exit()

# TTSPod modules
from remote_sync import sync as rsync
from config import Config
from content import Content
from links import Links
from pod import Pod
from speech import Speech
from ttspocket import TTSPocket
from ttsinsta import TTSInsta
from wallabag import Wallabag
from logger import Logger


class Main(object):
    def __init__(self, debug=False, engine=None, force=False, dry=False, clean=False, logfile=None, quiet=False):
        self.log = Logger(debug=debug, logfile=logfile, quiet=quiet)
        self.config = Config(engine=engine, log=self.log)
        self.p = None
        self.force = force
        self.dry = dry
        self.cache = []
        self.speech = Speech(config=self.config.speech,
                             dry=self.dry, log=self.log)
        self.loadCache(clean=clean)
        self.pod = Pod(self.config.pod, self.p)
        self.pod.config.debug = self.config.debug
        if self.dry:
            self.log.write("dry-run mode")

    def loadCache(self, clean=False):
        if self.config.cache_path:
            try:
                rsync(
                    source=self.config.cache_path,
                    destination=self.config.pickle,
                    debug=self.config.debug,
                    keyfile=self.config.ssh_keyfile,
                    password=self.config.ssh_password,
                    recursive=False
                )
                self.log.write(f'cache file synced successfully from server')
            except Exception as e:
                self.log.write(
                    f'something went wrong syncing the cache file {e}', True)
                if "code 23" in str(e):
                    self.log.write(
                        f'if this is your first time running TTSPod, this is normal since the cache has never been synced', True)
        if clean:
            self.log.write(
                f'moving {self.config.pickle} cache file and starting fresh')
            move(self.config.pickle, self.config.pickle +
                 str(int(datetime.datetime.now().timestamp())))
        if path.exists(self.config.pickle):
            try:
                with open(self.config.pickle, 'rb') as f:
                    [self.cache, self.p] = pickle.load(f)
            except:
                raise Exception(f"failed to open saved data file {f}")
        return True

    def process(self, items):
        if not items:
            self.log.write(f'no items found to process')
            return False
        for item in items[0:self.config.max_articles]:
            (title, content, url) = item
            if url in self.cache and not self.force:
                self.log.write(f'{title} is already in the feed, skipping')
                continue
            if len(content) > self.config.max_length:
                self.log.write(
                    f'{title} is longer than max length of {self.config.max_length}, skipping')
                continue
            self.log.write(f'processing {title}')
            fullpath = self.speech.speechify(title, content)
            if fullpath:
                self.pod.add((url, title, fullpath))
                self.cache.append(url)
            else:
                self.log.write(
                    f'something went wrong processing {title}', True)
        return True

    def saveCache(self):
        try:
            if self.pod:  # only save/sync cache if podcast data exists
                with open(self.config.pickle, 'wb') as f:
                    pickle.dump([self.cache, self.pod.p], f)
                if self.config.cache_path:
                    try:
                        rsync(
                            source=self.config.pickle,
                            destination=self.config.cache_path,
                            keyfile=self.config.ssh_keyfile,
                            debug=self.config.debug,
                            recursive=False,
                            size_only=False
                        )
                        self.log.write(
                            f'cache file synced successfully to server')
                    except Exception as e:
                        self.log.write(
                            f'something went wrong syncing the cache file {e}', True)
            else:
                self.log.write('cache save failed, no podcast data exists')
        except Exception as e:
            self.log.write(f'cache save failed {e}')

    def processWallabag(self, tag):
        wallabag = Wallabag(self.config.wallabag)
        items = wallabag.getItems(tag)
        return self.process(items)

    def processLink(self, url, title=None):
        links = Links(self.config.links)
        items = links.getItems(url, title)
        return self.process(items)

    def processPocket(self, tag):
        links = Links(self.config.links)
        p = TTSPocket(self.config.pocket, links)
        items = p.getItems(tag)
        return self.process(items)

    def processInsta(self, tag):
        links = Links(self.config.links)
        p = TTSInsta(self.config.insta, links)
        items = p.getItems(tag)
        return self.process(items)

    def processContent(self, text, title=None):
        content = Content(config=self.config.content, log=self.log)
        items = content.getItems(text, title)
        return self.process(items)

    def processFile(self, fname, title=None):
        content = Content(self.config.content)
        items = content.processFile(fname, title)
        return self.process(items)

    def finalize(self):
        if not self.dry:
            self.pod.save()
            self.pod.sync()
            self.saveCache()
        self.log.close()
        return True
