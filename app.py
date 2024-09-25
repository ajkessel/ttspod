#!/usr/bin/env python
try:
    import pip_system_certs.wrapt_requests # necessary to trust local SSL certificates, otherwise optional
except ImportError:
    pass

# third party modules
from dotenv import load_dotenv
import pypandoc
import datetime
import argparse
import validators
import magic
from pathlib import Path
from pydub import AudioSegment
from io import BytesIO
from shutil import copyfile, move
import os
import pickle
import re
import remote_sync
import sys
import validators

# TTSPod modules
from config import Config
from content import Content
from links import Links
from pod import Pod
from speech import Speech
from ttspocket import TTSPocket
from ttsinsta import TTSInsta
from wallabag import Wallabag

class Main(object):
    def __init__(self, debug = False, engine = None, force = False, dry = False):
        self.config = Config(debug = debug, engine = engine)
        self.p = None
        self.force = force
        self.dry = dry
        self.cache = []
        return
    def loadCache(self, debug = False, clean = False):
        if self.config.cache_path:
            try:
                remote_sync.sync(
                    source = self.config.cache_path,
                    destination = self.config.pickle,
                    debug = self.config.debug,
                    keyfile = self.config.ssh_keyfile,
                    password = self.config.ssh_password,
                    recursive = False
                    )
                if self.config.debug: print(f'cache file synced successfully from server')
            except Exception as e:
                print(f'something went wrong syncing the cache file {e}')
                if "code 23" in str(e):
                    print(f'if this is your first time running TTSPod, this is normal since the cache has never been synced')
        if clean:
            if self.config.debug: print(f'moving {self.config.pickle} cache file and starting fresh')
            move(self.config.pickle, self.config.pickle + str(int(datetime.datetime.now().timestamp())))
        if os.path.exists(self.config.pickle):
            try:
                with open(self.config.pickle, 'rb') as f:
                    [self.cache,self.p] = pickle.load(f)
            except:
                raise Exception(f"failed to open saved data file {f}")
        return True
    def process(self, items):
        for item in items[0:self.config.max_articles]:
            (title, content, url) = item
            if url in self.cache and not self.force:
                if self.config.debug: print(f'{title} is already in the feed, skipping')
                continue
            if len(content) > self.config.max_length:
                if self.config.debug: print(f'{title} is longer than max length of {self.config.max_length}, skipping')
                continue
            if self.config.debug: print(f'processing {title}')
            fullpath = self.speech.speechify(title, content)
            if fullpath:
                self.pod.add((url,title,fullpath))
                self.cache.append(url)
            else:
                if self.config.debug and not self.dry: print(f'something went wrong processing {title}')
    def saveCache(self):
        try:
            if self.pod: # only save/sync cache if podcast data exists
                with open(self.config.pickle, 'wb') as f:
                    pickle.dump([self.cache, self.pod.p], f)
                if self.config.cache_path:
                    try:
                        remote_sync.sync(
                            source = self.config.pickle,
                            destination = self.config.cache_path,
                            keyfile = self.config.ssh_keyfile,
                            debug = self.config.debug,
                            recursive = False,
                            size_only = False
                            )
                        if self.config.debug: print(f'cache file synced successfully to server')
                    except Exception as e:
                        print(f'something went wrong syncing the cache file {e}')
            else:
                if self.config.debug: print('cache save failed, no podcast data exists')
        except Exception as e:
            if self.config.debug: print(f'cache save failed {e}')
    def processWallabag(self, tag):
        wallabag = Wallabag(self.config.wallabag)
        items = wallabag.getItems(tag)
        return self.process(items)
    def processLink(self, url, title = None):
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
    def processContent(self, text, title = None):
        content = Content(self.config.content)
        items = content.getItems(text, title)
        return self.process(items)
    def processFile(self, fname, title = None):
        content = Content(self.config.content)
        items = content.processFile(fname, title)
        return self.process(items)
def main():
    parser = argparse.ArgumentParser(description='Convert any content to a podcast feed.')
    parser.add_argument('url', nargs = '*', action = 'store', type = str , default="", help="specify any number of URLs or local documents (plain text, HTML, PDF, Word documents, etc) to add to your podcast feed")
    parser.add_argument("-w", "--wallabag", nargs='?',const='audio', default="", help = "add unprocessed items with specified tag (default audio) from your wallabag feed to your podcast feed")
    parser.add_argument("-i", "--insta", nargs='?',const='audio', default="", help = "add unprocessed items with specified tag (default audio) from your instapaper feed to your podcast feed")
    parser.add_argument("-p", "--pocket", nargs='?',const='audio', default="", help = "add unprocessed items with specified tag (default audio) from your pocket feed to your podcast feed")
    parser.add_argument("-d", "--debug", action = 'store_true', help = "include debug output")
    parser.add_argument("-c", "--clean", action = 'store_true', help = "wipe cache clean and start new podcast feed")
    parser.add_argument("-f", "--force", action = 'store_true', help = "force addition of podcast even if cache indicates it has already been added")
    parser.add_argument("-t", "--title", action = 'store', help = "specify title for content provided via pipe")
    parser.add_argument("-e", "--engine", action = 'store', help = "specify TTS engine for this session (whisper, openai, eleven)")
    parser.add_argument("-s", "--sync", action = 'store_true', help = "sync podcast episodes and cache file")
    parser.add_argument("-n", "--dry-run", action = 'store_true', help = "dry run: do not actually create or sync audio files")
    args = parser.parse_args()
    debug = args.debug
    dry = args.dry_run
    force = args.force
    clean = args.clean
    title = args.title if hasattr(args,'title') else None
    engine = args.engine if hasattr(args,'engine') else None
    got_pipe = not os.isatty(sys.stdin.fileno())
    if not (args.url or args.wallabag or args.pocket or args.sync or got_pipe or args.insta):
        parser.print_help()
        exit()
    main = Main(debug = debug, engine = engine, force = force, dry = dry)
    main.loadCache(debug = debug, clean = clean)
    main.pod = Pod(main.config.pod, main.p)
    main.pod.config.debug = main.config.debug
    if main.config.debug and dry: print("dry-run mode") 
    main.speech = Speech(main.config.speech, dry)
    if got_pipe: main.processContent(str(sys.stdin.read()),title)
    if args.wallabag: main.processWallabag(args.wallabag)
    if args.pocket: main.processPocket(args.pocket)
    if args.insta: main.processInsta(args.insta)
    for i in args.url:
        if validators.url(i):
            main.processLink(i,title)
        elif os.path.isfile(i):
            main.processFile(i,title)
        else:
            print(f'argument {i} not recognized')  
    if not dry:
        main.pod.save()
        main.pod.sync()
        main.saveCache()
    return

if __name__ == "__main__":
    main()
