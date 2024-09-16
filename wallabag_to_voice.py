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
try:
    import numpy as np
    from grad_tts.model import GradTTS, params
    from grad_tts.text.symbols import symbols
    from grad_tts.text import text_to_sequence, cmudict
    from grad_tts.utils import intersperse
    from scipy.io.wavfile import write
    from grad_tts.model.hifi_gan.models import Generator as HiFiGAN
    from gradify import Gradify
    grad_available = True
except ImportError:
    grad_available = False
try:
    from TTS.api import TTS
    tts_available = True
except ImportError:
    tts_available = False

from dotenv import load_dotenv
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
        if (os.path.exists(self.pod_pickle)):
            with open(self.pod_pickle, 'rb') as f:
                self.p = pickle.load(f)
        self.cache = []
        if self.p:
            for ep in self.p.episodes:
                self.cache.append(ep.summary)
        else:
            self.p = self.newPod()
        return

    def loadConfig(self):
        global openai_available
        global eleven_available
        global tortoise_available
        global grad_available
        global tts_available
        load_dotenv()
        self.debug = 'wallpod_debug' in os.environ
        self.wallabagUrl = os.environ['url']
        self.username = os.environ['user']
        self.password = os.environ['password']
        self.client_id = os.environ['client']
        self.secret = os.environ['secret']
        self.working_path = os.path.join(os.environ['working_path'], '') if 'working_path' in os.environ else "./working"
        self.pod_url = os.environ['pod_url']
        self.temp_path = f'{self.working_path}temp/'
        self.final_path = f'{self.working_path}wallabag/'
        self.pod_pickle = f'{self.working_path}wallabag.pickle'
        self.pod_rss_url = f'{self.pod_url}/index.rss' 
        self.pod_rss_file = f'{self.final_path}index.rss'
        self.max_length = int(os.environ['wallpod_max_length']) if 'max_length' in os.environ else 20000
        self.ssh_server = os.environ['ssh_server'] if 'ssh_server' in os.environ else ""
        self.ssh_server_path = os.path.join(os.environ['ssh_server_path'],'') if 'ssh_server_path' in os.environ else ""
        self.eleven_api_key = os.environ['eleven_api_key'] if 'eleven_api_key' in os.environ else ""
        self.openai_api_key = os.environ['openai_api_key'] if 'openai_api_key' in os.environ else ""
        self.engine = os.environ['engine'].lower() if 'engine' in os.environ else ""
        self.grad_tts = os.environ['grad_tts'] if 'grad_tts' in os.environ else ""
        self.hifigan = os.environ['hifigan'] if 'hifigan' in os.environ else ""
        self.pe_scale = int(os.environ['pe_scale']) if 'pe_scale' in os.environ else None
        self.n_spks = int(os.environ['n_spks']) if 'pe_scale' in os.environ else None
        self.tts_model = os.environ['wallpod_tts_model'] if 'wallpod_tts_model' in os.environ else None
        self.tts_vocoder_model = os.environ['wallpod_tts_vocoder_model'] if 'wallpod_tts_vocoder_model' in os.environ else None
        if self.engine in 'openai' and self.openai_api_key and openai_available:
            self.engine = 'openai'
            self.tts = OpenAI(api_key = self.openai_api_key)
            self.openai_voice = os.environ['wallpod_openai_voice'] if 'wallpod_openai_voice' in os.environ else "onyx"
            self.openai_model = os.environ['wallpod_openai_model'] if 'wallpod_openai_model' in os.environ else "tts-1-hd"
        elif self.engine in 'eleven' and self.eleven_api_key and eleven_available:
            self.engine = 'eleven'
            self.elevenclient = ElevenLabs(
                api_key=self.eleven_api_key
                )
        elif self.engine in 'tortoise' and tortoise_available:
            self.engine = 'tortoise'
            self.tts = TextToSpeech(kv_cache=True, half=True)
            self.voice_samples, self.conditioning_latents = load_voices(['daniel'])
        elif self.engine in 'grad' and grad_available and self.grad_tts and self.hifigan:
            self.engine = 'grad'
            self.tts = Gradify(self.grad_tts, self.hifigan,self.pe_scale,self.n_spks)
        elif self.engine in 'tts' and self.tts_model and tts_available:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if self.tts_vocoder_model:
                self.tts = TTS(model_name = self.tts_model, vocoder_path = self.tts_vocoder_model).to(device)
            else:
                self.tts = TTS(model_name = self.tts_model).to(device)
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
        if self.debug: print(self.username)
        if self.debug: print(token)
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
        elif self.ssh_server_path:
            sysrsync.run(source=self.final_path,
                destination=self.ssh_server_path,
                sync_source_contents=True,
                options=['-a']
                )
        else:
            if self.debug: print("ssh_server_path not defined so not uploading results")


    def speechify(self, title, text):
        out_file = self.final_path + slugify(title) + ".mp3"
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
        combined = AudioSegment.empty()
        for (item,segment) in enumerate(segments):
            segment_audio = f'{self.temp_path}{item}.mp3'
            if self.debug: print(f'processing text #{item} length {len(segment)}:\n{segment}\n--------------------')
            try:
                if self.engine == "eleven":
                    audio = self.elevenclient.generate(
                        text=segment,
                        voice="Daniel",
                        model="eleven_monolingual_v1"
                        )
                    save(audio, segment_audio)
                elif self.engine == "openai":
                    response = self.tts.audio.speech.create(
                        model=self.openai_model,
                        voice=self.openai_voice,
                        input=segment
                        )
                    response.stream_to_file(segment_audio)
                elif self.engine == 'tortoise':
                    gen, dbg_state = self.tts.tts_with_preset(text=segment, k=1, voice_samples=self.voice_samples, conditioning_latents=self.conditioning_latents,
                                    preset='fast', return_deterministic_state=True, cvvp_amount=0)
                    torchaudio.save(segment_audio, gen.squeeze(0).cpu(), 24000)
                elif self.engine == 'grad':
                    self.tts.transcribe(segment,segment_audio,200)
                elif self.engine == 'tts':
                    self.tts.tts_to_file(text=segment,file_path="output.wav",split_sentences=False)
                    AudioSegment.from_file("output.wav").export(segment_audio,format='mp3')
                    # TODO use BytesIO and perform in RAM
                else:
                    raise Exception("no TTS engine found")
            except:
                print("TTS failed")
            else:
                combined += AudioSegment.from_mp3(segment_audio)
        combined.export(out_file, format="mp3")
        os.chmod(out_file, 0o644)
        return (out_file)

    def process(self):
        entries = self.getEntries()
        for entry in entries:
            (title, content, url) = entry
            if url in self.cache:
                if self.debug: print(f'{title} is already in the feed, skipping')
                continue
            if len(content) > self.max_length:
                if self.debug: print(f'{title} is longer than max length of {self.max_length}, skipping')
                continue
            if self.debug: print(f'processing {title}')
            fullpath = self.speechify(title, content)
            filename = ntpath.split(fullpath)[1]
            size = os.path.getsize(f'{fullpath}')
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