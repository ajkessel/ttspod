#!/usr/bin/env python
try:
    import pip_system_certs.wrapt_requests # necessary to trust local SSL certificates, otherwise optional
except ImportError:
    pass
try:
    import trafilatura # to extract readable content from webpages
    trafilatura_available = True
except ImportError:
    trafilatura_available = False
try:
    from openai import OpenAI # TTS with OpenAI
    openai_available = True
except ImportError:
    openai_available = False
try:
    from elevenlabs.client import ElevenLabs # TTS with Eleven
    from elevenlabs import save
    eleven_available = True
except ImportError:
    eleven_available = False 
try:
    from whisperspeech.pipeline import Pipeline
    whisper_available = True
except ImportError:
    whisper_available = False

from dotenv import load_dotenv
import argparse
import validators
from pathlib import Path
from pydub import AudioSegment
from io import BytesIO
import html2text
import json
import ntpath
import os
import pickle
import pod2gen
import re
import requests
import sysrsync
import sys
import unicodedata

from config import Config
from content import Content
from links import Links
from pod import Pod
from speech import Speech
from ttspocket import TTSPocket
from wallabag import Wallabag

class Main(object):
    def __init__(self, debug = False):
        self.config = Config(debug)
        self.p = None
        self.cache = []
        self.pod = None
        if (os.path.exists(self.config.pickle)):
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
            if url in self.cache:
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
    parser.add_argument('url', nargs = '*', action = 'store', type = str , default="", help="specify any number of URLs to add to your podcast feed")
    parser.add_argument("-w", "--wallabag", nargs='?',const='audio', default="", help = "add unprocessed items with specified tag (default audio) from your wallabag feed to your podcast feed")
    parser.add_argument("-p", "--pocket", nargs='?',const='audio', default="", help = "add unprocessed items with specified tag (default audio) from your pocket feed to your podcast feed")
    parser.add_argument("-d", "--debug", action = 'store_true', help = "include debug output")
    parser.add_argument("-t", "--title", action = 'store', help = "specify title for content provided via pipe")
    args = parser.parse_args()
    debug = hasattr(args,'debug')
    got_pipe = not os.isatty(sys.stdin.fileno())
    main = Main(debug)
    if got_pipe: main.processContent(sys.stdin.read())
    if args.url: main.processLinks(args.url)
    if args.wallabag: main.processWallabag(args.wallabag)
    if args.pocket: main.processPocket(args.pocket)
    main.pod.save()
    main.pod.sync()
    main.saveCache()
    return

if __name__ == "__main__":
    main()
