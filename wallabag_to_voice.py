#!/usr/bin/env python
from pathlib import Path
import pickle
import unicodedata
import re
import requests
import json
import html2text
import pod2gen
from dotenv import load_dotenv
import os
import sys
import tempfile
import time
import torch
import torchaudio
from tortoise.api import MODELS_DIR, TextToSpeech
from tortoise.utils.audio import get_voices, load_voices, load_audio
from tortoise.utils.text import split_and_recombine_text
from pydub import AudioSegment

def slugify(value):
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

class WallPod(object):
    def __init__(self):
        self.loadConfig()
        self.p = None
        Path(self.working_path).mkdir(parents=True, exist_ok=True)
        Path(self.temp_path).mkdir(parents=True, exist_ok=True)
        Path(self.final_path).mkdir(parents=True, exist_ok=True)
        return

    def loadConfig(self):
        load_dotenv()
        self.url = os.environ['url']
        self.username = os.environ['user']
        self.password = os.environ['password']
        self.client = os.environ['client']
        self.secret = os.environ['secret']
        self.working_path = os.environ['working_path']
        self.temp_path = f'{self.working_path}/temp'
        self.final_path = f'{self.working_path}/wallabag'
        self.pod_pickle = f'{self.working_path}/wallabag.pickle'
        self.pod_url = 'https://podcast.rosi-kessel.org/wallabag'
        self.pod_rss_url = f'{self.pod_url}/index.rss'
        self.pod_rss_file = f'{self.final_path}/index.rss'
        return

    def getEntries(self):
        entries_url = f'{self.url}/api/entries.json?starred=1&sort=created&order=asc&page=1&perPage=500&since=0&detail=full'
        auth_url = f'{self.url}/oauth/v2/token'
        auth_data = { 'username': self.username,
                    'password': self.password,
                    'client_id': self.client,
                    'client_secret': self.secret,
                    'grant_type' : 'password' }
        login = requests.post(auth_url, data = auth_data)
        token = json.loads(login.content)
        print(self.username)
        access_token = token['access_token']
        headers = {"Authorization": f"Bearer {access_token}"}
        entries_request = requests.get(entries_url, headers = headers)
        entries_response = json.loads(entries_request.content)
        entries = entries_response['_embedded']['items']
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        all_entries = []
        for entry in entries:
            uid = entry['uid']
            title = entry['title']
            text = h.handle(entry['content'])
            this_entry = (uid,title,text)
            all_entries.append(this_entry)
        return all_entries

    def newPod(self):
        pod = pod2gen.Podcast()
        pod.name = "Wallabag Feed"
        pod.website = self.pod_rss_url
        pod.feed_url = self.pod_rss_url
        pod.description = 'A custom podcast feed just for wallabag'
        pod.author = 'Adam Kessel'
        pod.image = f'{self.pod_url}/icon.png'
        pod.language = 'en-us'
        pod.explicit = False
        pod.generate_guid()
        return pod

    def saveFeed(self):
        self.p.rss_file(self.pod_rss_file,minimize=False)

    def speechify(self, title, text):
        out_file = slugify(title) + ".mp3"
        paragraphs = split_and_recombine_text(text)
        tts = TextToSpeech(models_dir=MODELS_DIR, use_deepspeed=False, kv_cache=True, half=True, enable_redaction=False, device="cuda")
        voice_samples, conditioning_latents = load_voices(['daniel'])
        item = 1
        combined = AudioSegment.empty()
        for para in paragraphs:
            gen, dbg_state = tts.tts_with_preset(para, k=1, voice_samples=voice_samples, conditioning_latents=conditioning_latents,
                                        preset='ultra_fast', use_deterministic_seed=None, return_deterministic_state=True, cvvp_amount=0)
            torchaudio.save(f'{self.temp_path}/{item}.wav', gen.squeeze(0).cpu(), 24000)
            combined += AudioSegment.from_wav(f'{self.temp_path}/{item}.wav')
            item += 1
        #combined.export(f'{final_path}/{out_file}',format="mp3", tag={'title': title})
        combined.export(f'{self.final_path}/{out_file}',format="mp3")
        return(out_file)

    def process(self):
        entries = self.getEntries()
        item = 1
        if (os.path.exists(self.pod_pickle)):
            with open(self.pod_pickle, 'rb') as f:
                self.p = pickle.load(f)
        cached = []
        if self.p:
            for ep in self.p.episodes:
                cached.append(ep.title)         
        else:
            self.p = self.newPod()
        for entry in entries:
            (uid,title,content) = entry
            if title in cached:
                print(f'{title} is already in the feed, skipping')
                continue
            print(f'processing {title}')
            filename = self.speechify(title, content)
            size = os.path.getsize(f'{self.final_path}/{filename}')
            self.p.episodes.append(
            pod2gen.Episode(
                title=title,
                media=pod2gen.Media(f'{self.pod_url}/{filename}',size)
                )
            )
        self.saveFeed()
        with open(self.pod_pickle, 'wb') as f:
            pickle.dump(self.p,f)
        
def main():
    success = WallPod()
    success.process()
    return

if __name__ == '__main__':
    main()