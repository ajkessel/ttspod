"""main module for triggering input and output modules"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from os import path
    from shutil import move
    import datetime
    import pickle
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# TTSPod modules
from config import Config
from content import Content
from links import Links
from logger import Logger
from pod import Pod
from remote_sync import sync as rsync
# TODO: use native rsync on platforms where it is available
from speech.speech import Speech
from ttsinsta import TTSInsta
from ttspocket import TTSPocket
from wallabag import Wallabag


class Main(object):
    """main orchestrating object"""

    def __init__(self, debug=False, config_path=None, engine=None,
                 force=False, dry=False, clean=False, logfile=None,
                 quiet=False, gpu=None):
        self.log = Logger(debug=debug, logfile=logfile, quiet=quiet)
        self.config = Config(
            engine=engine, config_path=config_path, log=self.log, gpu=gpu, quiet=quiet, debug=debug
        )
        self.p = None
        self.force = force
        self.dry = dry
        self.cache = []
        self.speech = None  # defer spinning up TTS until necessary
        self.load_cache(clean=clean)
        self.pod = Pod(config=self.config.pod, p=self.p, log=self.log)
        self.pod.config.debug = self.config.debug
        if self.dry:
            self.log.write("dry-run mode")

    def load_cache(self, clean=False):
        """load podcast and cache from pickle if available"""
        if self.config.state_file_path:
            try:
                rsync(
                    source=self.config.state_file_path,
                    destination=self.config.pickle,
                    debug=self.config.debug,
                    keyfile=self.config.ssh_keyfile,
                    password=self.config.ssh_password,
                    recursive=False
                )
                self.log.write('state file synced successfully from server')
            except Exception as err:  # pylint: disable=broad-except
                self.log.write(
                    f'something went wrong syncing the state file {err}', True)
                if "code 23" in str(err):
                    self.log.write(
                        'if this is your first time running TTSPod, '
                        'this is normal since the cache has never been synced',
                        True)
        if clean:
            self.log.write(
                f'moving {self.config.pickle} state file and starting fresh')
            move(self.config.pickle, self.config.pickle +
                 str(int(datetime.datetime.now().timestamp())))
        if path.exists(self.config.pickle):
            try:
                with open(self.config.pickle, 'rb') as f:
                    [self.cache, self.p] = pickle.load(f)
            except Exception as err:
                raise ValueError(
                    f"failed to open saved data file {f}: {err}") from err
        return True

    def process(self, items):
        """feed items retrieved by input modules to TTS output modules"""
        if not items:
            self.log.write('no items found to process')
            return False
        if not self.speech:
            self.speech = Speech(config=self.config.speech,
                                 dry=self.dry, log=self.log)
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

    def save_cache(self):
        """save cache and podcast pickle"""
        try:
            if self.pod:  # only save/sync cache if podcast data exists
                with open(self.config.pickle, 'wb') as f:
                    pickle.dump([self.cache, self.pod.p], f)
                if self.config.state_file_path:
                    try:
                        rsync(
                            source=self.config.pickle,
                            destination=self.config.state_file_path,
                            keyfile=self.config.ssh_keyfile,
                            debug=self.config.debug,
                            recursive=False,
                            size_only=False
                        )
                        self.log.write(
                            'state file synced successfully to server')
                    except Exception as err:  # pylint: disable=broad-except
                        self.log.write(
                            f'something went wrong syncing the state file {err}', True)
            else:
                self.log.write('cache save failed, no podcast data exists')
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(f'cache save failed {err}')

    def process_wallabag(self, tag):
        """process wallabag items matching tag"""
        wallabag = Wallabag(config=self.config.wallabag, log=self.log)
        items = wallabag.get_items(tag)
        return self.process(items)

    def process_link(self, url, title=None):
        """process link content from URL"""
        links = Links(config=self.config.links, log=self.log)
        items = links.get_items(url, title)
        return self.process(items)

    def process_pocket(self, tag='audio'):
        """process pocket items matching tag"""
        links = Links(config=self.config.links, log=self.log)
        p = TTSPocket(config=self.config.pocket, links=links, log=self.log)
        items = p.get_items(tag)
        return self.process(items)

    def process_insta(self, tag):
        """process instapaper items matching tag"""
        links = Links(self.config.links)
        p = TTSInsta(config=self.config.insta, links=links, log=self.log)
        items = p.get_items(tag)
        return self.process(items)

    def process_content(self, text, title=None):
        """process any sort of text content"""
        content = Content(config=self.config.content, log=self.log)
        items = content.get_items(text, title)
        return self.process(items)

    def process_file(self, fname, title=None):
        """process input from files"""
        content = Content(config=self.config.content, log=self.log)
        items = content.process_file(fname, title)
        return self.process(items)

    def finalize(self):
        """finalize session by saving and syncing podcast and cache"""
        if not self.dry:
            self.pod.save()
            self.pod.sync()
            self.save_cache()
        self.log.close()
        return True
