#!/usr/bin/env python
try:
    import pip_system_certs.wrapt_requests # necessary to trust local SSL certificates, otherwise optional
except ImportError:
    pass

# third party modules
from dotenv import load_dotenv
import datetime
import argparse
import validators
from pathlib import Path
from pydub import AudioSegment
from io import BytesIO
from shutil import copyfile, move
import html2text
import json
import ntpath
import os
import pickle
import pod2gen
import re
import requests
from sysrsync import run as rsync
import sys
import unicodedata

# TTSPod modules
from config import Config
from content import Content
from links import Links
from pod import Pod
from speech import Speech
from ttspocket import TTSPocket
from wallabag import Wallabag

class Main(object):
    def __init__(self, debug = False, engine = None, force = False, wipe = False):
        self.config = Config(debug = debug, engine = engine)
        self.p = None
        self.force = force
        self.cache = []
        self.pod = None
        if self.config.cache_path:
            if self.config.cache_path.startswith("ssh://"):
                try:
                    (domain,path)=re.match(r'ssh://([^/]*)(.*)$',self.config.cache_path).group(1,2)
                    rsync(source=f'{path}',
                        source_ssh=domain,
                        destination=self.config.pickle,
                        sync_source_contents=False
                        )
                    if self.config.debug: print(f'cache file synced successfully')
                except Exception as e:
                    print(f'something went wrong syncing the cache file {e}')
                    if "code 23" in str(e):
                        print(f'if this is your first time running TTSPod, this is normal since the cache has never been synced')
            else:
                try:
                    copyfile(f'{path}/ttspod.pickle',self.config.pickle)
                    if self.config.debug: print(f'cache file synced successfully')
                except Exception as e:
                    print(f'something went wrong syncing the cache file {e}')
        if wipe:
            if self.config.debug: print(f'moving {self.config.pickle} cache file and starting fresh')
            move(self.config.pickle, self.config.pickle + int(datetime.datetime.now().timestamp()))
        if os.path.exists(self.config.pickle):
            try:
                with open(self.config.pickle, 'rb') as f:
                    [self.cache,self.pod] = pickle.load(f)
            except:
                raise Exception(f"failed to open saved data file {f}")
        if not self.pod:
            self.pod = Pod(self.config.pod)
        self.speech = Speech(self.config.speech)
        return

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
                if self.config.debug: print(f'something went wrong processing {title}')
    
    def saveCache(self):
        try:
            if self.cache and self.pod:
                with open(self.config.pickle, 'wb') as f:
                    pickle.dump([self.cache, self.pod], f)
                if self.config.cache_path:
                    if self.config.cache_path.startswith("ssh://"):
                        try:
                            (domain,path)=re.match(r'ssh://([^/]*)(.*)$',self.config.cache_path).group(1,2)
                            rsync(source=self.config.pickle,
                                destination=path,
                                destination_ssh=domain,
                                sync_source_contents=False
                                )
                            if self.config.debug: print(f'cache file synced successfully')
                        except Exception as e:
                            print(f'something went wrong syncing the cache file {e}')
                    else:
                        try:
                            copyfile(self.config.pickle, self.config.cache_path)
                            if self.config.debug: print(f'cache file synced successfully')
                        except Exception as e:
                            print(f'something went wrong syncing the cache file {e}')
            else:
                if self.config.debug: print('cache save failed')
        except Exception as e:
            if self.config.debug: print(f'cache save failed {e}')
            
    def processWallabag(self,tag):
        wallabag = Wallabag(self.config.wallabag)
        items = wallabag.getItems(tag)
        self.process(items)
        return
        
    def processLinks(self,urls):
        links = Links(self.config.links)
        items = links.getItems(urls)
        self.process(items)
        return

    def processPocket(self,tag):
        p = TTSPocket(self.config.pocket)
        items = p.getItems(tag)
        self.process(items)
        return

    def processContent(self, text, title = None):
        content = Content(self.config.content)
        items = content.getItems(text, title)
        self.process(items)
        return

def main():
    parser = argparse.ArgumentParser(description='Convert any content to a podcast feed.')
    parser.add_argument('url', nargs = '*', action = 'store', type = str , default="", help="specify any number of URLs or local files to add to your podcast feed")
    parser.add_argument("-w", "--wallabag", nargs='?',const='audio', default="", help = "add unprocessed items with specified tag (default audio) from your wallabag feed to your podcast feed")
    parser.add_argument("-p", "--pocket", nargs='?',const='audio', default="", help = "add unprocessed items with specified tag (default audio) from your pocket feed to your podcast feed")
    parser.add_argument("-d", "--debug", action = 'store_true', help = "include debug output")
    parser.add_argument("-c", "--clean", action = 'store_true', help = "wipe cache clean and start new podcast feed")
    parser.add_argument("-f", "--force", action = 'store_true', help = "force addition of podcast even if cache indicates it has already been added")
    parser.add_argument("-t", "--title", action = 'store', help = "specify title for content provided via pipe")
    parser.add_argument("-e", "--engine", action = 'store', help = "specify TTS engine for this session (whisper, openai, eleven)")
    
    args = parser.parse_args()
    debug = hasattr(args, 'debug')
    force = hasattr(args, 'force')
    wipe = hasattr(args, 'wipe')
    title = args.title if hasattr(args,'title') else None
    engine = args.engine if hasattr(args,'engine') else None
    got_pipe = not os.isatty(sys.stdin.fileno())
    main = Main(debug = debug, engine = engine, force = force, wipe = wipe)
    if got_pipe: main.processContent(str(sys.stdin.read()),title)
    if args.url: main.processLinks(args.url)
    if args.wallabag: main.processWallabag(args.wallabag)
    if args.pocket: main.processPocket(args.pocket)
    main.pod.save()
    main.pod.sync()
    main.saveCache()
    return

if __name__ == "__main__":
    main()
