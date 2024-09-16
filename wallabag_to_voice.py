#!/usr/bin/env python
try:
    import pip_system_certs.wrapt_requests # necessary to trust local SSL certificates, otherwise optional
except ImportError:
    pass
try:
    from openai import OpenAI
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning) # necessary for OpenAI TTS streaming
    openai_available = True
except ImportError:
    openai_available = False
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import save
    eleven_available = True
except ImportError:
    eleven_available = False 
try:
    import torch
    import torchaudio
    from tortoise.api import TextToSpeech, MODELS_DIR
    from tortoise.utils.audio import load_voices
    from tortoise.utils.text import split_and_recombine_text
    tortoise_available = True
except ImportError:
    tortoise_available = False
from dotenv import load_dotenv
from pathlib import Path
from pydub import AudioSegment
import html2text
import json
import os
import pickle
import pod2gen
import re
import requests
import sysrsync
import unicodedata

def slugify(value):
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode(
        'ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

class WallPod(object):
    def __init__(self):
        self.loadConfig()
        self.p = None
        Path(self.working_path).mkdir(parents=True, exist_ok=True)
        Path(self.temp_path).mkdir(parents=True, exist_ok=True)
        Path(self.final_path).mkdir(parents=True, exist_ok=True)
        os.chmod(self.final_path, 0o755)
        return

    def loadConfig(self):
        global openai_available
        global eleven_available
        global tortoise_available
        load_dotenv()
        self.wallabagUrl = os.environ['url']
        self.username = os.environ['user']
        self.password = os.environ['password']
        self.client_id = os.environ['client']
        self.secret = os.environ['secret']
        self.working_path = os.path.join(os.environ['working_path'], '')
        self.pod_url = os.environ['pod_url']
        self.temp_path = f'{self.working_path}temp/'
        self.final_path = f'{self.working_path}wallabag/'
        self.pod_pickle = f'{self.working_path}wallabag.pickle'
        self.pod_rss_url = f'{self.pod_url}/index.rss'
        self.pod_rss_file = f'{self.final_path}index.rss'
        self.ssh_server = os.environ['ssh_server'] if 'ssh_server' in os.environ else ""
        self.ssh_server_path = os.path.join(os.environ['ssh_server_path'],'') if 'ssh_server_path' in os.environ else ""
        self.eleven_api_key = os.environ['eleven_api_key'] if 'eleven_api_key' in os.environ else ""
        self.openai_api_key = os.environ['openai_api_key'] if 'openai_api_key' in os.environ else ""
        self.engine = os.environ['engine'].lower() if 'engine' in os.environ else ""
        if self.engine in 'openai' and self.openai_api_key and openai_available:
            self.engine = 'openai'
            self.openaiclient = OpenAI(api_key = self.openai_api_key)
        elif self.engine in 'eleven' and self.eleven_api_key and eleven_available:
            self.engine = 'eleven'
            self.elevenclient = ElevenLabs(
                api_key=self.eleven_api_key
                )
        elif self.engine in 'tortoise' and tortoise_available:
            self.engine = 'tortoise'
            self.tts = TextToSpeech(kv_cache=True, half=True)
            self.voice_samples, self.conditioning_latents = load_voices(['daniel'])
        else:
            raise Exception("no TTS engine/API key found")
        return

    def getEntries(self):
        entries_url = f'{self.wallabagUrl}/api/entries.json?starred=1&sort=created&order=asc&page=1&perPage=500&since=0&detail=full'
        auth_url = f'{self.wallabagUrl}/oauth/v2/token'
        auth_data = {'username': self.username,
                     'password': self.password,
                     'client_id': self.client_id,
                     'client_secret': self.secret,
                     'grant_type': 'password'}
        login = requests.post(auth_url, data=auth_data)
        token = json.loads(login.content)
        print(self.username)
        print(token)
        access_token = token['access_token']
        headers = {"Authorization": f"Bearer {access_token}"}
        entries_request = requests.get(entries_url, headers=headers)
        entries_response = json.loads(entries_request.content)
        entries = entries_response['_embedded']['items']
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        all_entries = []
        for entry in entries:
            title = entry['title']
            text = h.handle(entry['content'])
            url = h.handle(entry['url'])
            this_entry = (title, text, url)
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
        self.p.rss_file(self.pod_rss_file, minimize=False)
        os.chmod(self.pod_rss_file, 0o644)

    def syncFeed(self):
        if self.ssh_server_path and self.ssh_server:
            sysrsync.run(source=self.final_path,
                destination=self.ssh_server_path,
                destination_ssh=self.ssh_server,
                sync_source_contents=True,
                options=['-a']
                )

    def speechify(self, title, text):
        out_file = slugify(title) + ".mp3"
        paragraphs = re.split(r'(\n|\r){2,}',text)
        segments = []
        add_to_next = ""
        if self.engine != "tortoise":
            for para in paragraphs:
                this_segment = (add_to_next + re.sub(' +',' ',para))
                if not re.search('[A-Za-z]{5}',this_segment):
                    continue
                if len(this_segment) < 50:
                    add_to_next = this_segment
                    continue
                else:
                    add_to_next = ""
                if len(this_segment) > 4096:
                    this_segment = re.sub(r'([A-Za-z]{5}\.) +',r'\1-----',this_segment)
                    new_segments = re.split('-----',this_segment)
                    segments.extend([x.replace("-----"," ") for x in new_segments])
                else:
                    segments.append(this_segment)
        else:
            segments = split_and_recombine_text(text)
        item = 1
        combined = AudioSegment.empty()
        for segment in segments:
            print(f'processing {segment}')
            if self.engine == "eleven":
                audio = self.elevenclient.generate(
                    text=segment,
                    voice="Daniel",
                    model="eleven_monolingual_v1"
                    )
                save(audio, f'{self.temp_path}{item}.mp3')
            elif self.engine == "openai":
                response = self.openaiclient.audio.speech.create(
                    model="tts-1",
                    voice="alloy",
                    input=segment
                    )
                response.stream_to_file(f'{self.temp_path}{item}.mp3')
            elif self.engine == 'tortoise':
                gen, dbg_state = self.tts.tts_with_preset(text=segment, k=1, voice_samples=self.voice_samples, conditioning_latents=self.conditioning_latents,
                                  preset='fast', return_deterministic_state=True, cvvp_amount=1)
                torchaudio.save(f'{self.temp_path}{item}.mp3', gen.squeeze(0).cpu(), 24000)
            combined += AudioSegment.from_mp3(f'{self.temp_path}{item}.mp3')
        combined.export(f'{self.final_path}{out_file}', format="mp3")
        os.chmod(f'{self.final_path}{out_file}', 0o644)
        return (out_file)

    def process(self):
        entries = self.getEntries()
        item = 1
        if (os.path.exists(self.pod_pickle)):
            with open(self.pod_pickle, 'rb') as f:
                self.p = pickle.load(f)
        cached = []
        if self.p:
            for ep in self.p.episodes:
                cached.append(ep.summary)
        else:
            self.p = self.newPod()
        for entry in entries:
            (title, content, url) = entry
            if url in cached:
                print(f'{title} is already in the feed, skipping')
                continue
            print(f'processing {title}')
            filename = self.speechify(title, content)
            size = os.path.getsize(f'{self.final_path}{filename}')
            self.p.episodes.append(
                pod2gen.Episode(
                    title = title,
                    summary = url,
                    long_summary = f'Text to speech by {self.engine} from {url}',
                    media=pod2gen.Media(f'{self.pod_url}/{filename}', size)
                )
            )
        self.saveFeed()
        self.syncFeed()
        with open(self.pod_pickle, 'wb') as f:
            pickle.dump(self.p, f)


def main():
    wallpod = WallPod()
    wallpod.process()
    return

if __name__ == '__main__':
    main()
