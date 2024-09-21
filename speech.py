import os
import unicodedata
import re
import textwrap
import uuid
import warnings
from pathlib import Path
from anyascii import anyascii
from pydub import AudioSegment

try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize, BlanklineTokenizer
except:
    pass
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import save
except:
    pass
try:
    from whisperspeech.pipeline import Pipeline
    import torch
    import torchaudio
    warnings.filterwarnings("ignore") # to suppress TTS output
    whisper_available = True
except ImportError:
    whisper_available = False
try:
    from openai import OpenAI
    warnings.filterwarnings("ignore", category=DeprecationWarning) # necessary for OpenAI TTS streaming
    openai_available = True
except:
    openai_available = False
    pass
try:
    from elevenlabs.client import ElevenLabs # TTS with Eleven
    from elevenlabs import save
    eleven_available = True
except ImportError:
    eleven_available = False 

class Speech(object):
    def __init__(self, config):
        self.config = config
        self.config.nltk = False
        self.final_path = config.final_path
        match self.config.engine:
            case "openai":
                self.tts = OpenAI(api_key = self.config.openai_api_key)
            case "eleven":
                self.tts = ElevenLabs(api_key = self.config.eleven_api_key)
            case "whisper":
                self.tts = Pipeline(t2s_ref=self.config.whisper_t2s_model, s2a_ref=self.config.whisper_s2a_model, torch_compile = True, device=self.config.device, optimize = True)
            case _:
                raise Exception('TTS engine not configured')
        try:
            nltk.data.find('tokenizers/punkt_tab')
            self.config.nltk = True
        except LookupError:
            try:
                nltk.download('punkt_tab')
                self.config.nltk = True
            except:
                pass
    def slugify(self, value):
        value = str(value)
        value = unicodedata.normalize('NFKD', value).encode(
            'ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value.lower())
        return re.sub(r'[-\s]+', '-', value).strip('-_')
    def speechify(self, title = "missing", raw_text = ""):
        out_file = self.config.final_path + self.slugify(title) + ".mp3"
        text = anyascii(raw_text)
        temp = str(uuid.uuid4())
        if os.path.exists(out_file):
            out_file = self.config.final_path + self.slugify(title) + "-" + temp + ".mp3"
        if self.config.engine == "whisper":
            chunks = self.split_and_prepare_text(text)
            self.whisper_long(chunks=chunks,output=out_file,speaker=self.config.whisper_voice)
            os.chmod(out_file, 0o644)
            return (out_file)
        if self.config.nltk:
            paragraphs = BlanklineTokenizer().tokenize(text)
        else:
            paragraphs = text.split('\n\n')
        segments = []
        for para in paragraphs:
            if self.config.debug: print(f"paragraph {para}")
            if len(para) < 8: # skip very short lines which are likely not text
                continue
            if len(para) > 4096: # break paragraphs greater than 4096 characters into sentences
                if self.config.debug: print(f"further splitting paragraph of length {len(para)}")
                if self.config.nltk:
                    sentences = sent_tokenize(para)
                else:
                    sentences = textwrap.wrap(4096)
                for sentence in sentences:
                    if len(sentence) > 4096: # break sentences greater than 4096 characters into smaller pieces
                        chunks = textwrap.wrap(4096)
                        for chunk in chunks:
                            if len(chunk) < 4096:
                                segments.append(chunk)
                            else: # if we can't find pieces smaller than 4096 characters, we give up
                                if self.config.debug: print("abnormal sentence fragment found, skipping")
                    else:
                        segments.append(sentence)
            else:
                segments.append(para)
        combined = AudioSegment.empty()
        for (item,segment) in enumerate(segments):
            segment_audio = f'{self.config.temp_path}-{temp}-{item}.mp3'
            if self.config.debug: print(f'processing text #{item+1} out of {len(segments)}\nitem length {len(segment)}:\n{segment}\n--------------------')
            try:
                if self.config.engine == "eleven":
                    audio = self.tts.generate(
                        text=segment,
                        voice=self.config.eleven_voice,
                        model=self.config.eleven_model
                        )
                    save(audio, segment_audio)
                elif self.config.engine == "openai":
                    response = self.tts.audio.speech.create(
                        model = self.config.openai_model,
                        voice = self.config.openai_voice,
                        input = segment
                        )
                    response.stream_to_file(segment_audio)
                if self.config.debug: print(f'segment successful')
                combined += AudioSegment.from_mp3(segment_audio)
            except Exception as e:
                if self.config.debug: print(f'TTS failed {e}')
        try:
            if combined.duration_seconds > 2:
                combined.export(out_file, format="mp3")
                os.chmod(out_file, 0o644)
                if self.config.debug: print(f'final audio successful')
                return (out_file)
            else:
                if self.config.debug: print(f'did not generate a long enough file')
                return None
        except Exception as e:
            if self.config.debug: print(f'TTS failed {e}')
        return None
    
    def split_and_prepare_text(self, text, cps=14):
        chunks = []
        sentences = sent_tokenize(text)
        chunk = ""
        for sentence in sentences:
            sentence = re.sub('[()]', ",", sentence).strip()
            sentence = re.sub(",+", ",", sentence)
            sentence = re.sub('"+', "", sentence)
            if len(chunk) + len(sentence) < 20*cps:
                chunk += " " + sentence
            elif chunk:
                chunks.append(chunk)
                chunk = sentence
            elif sentence:
                chunks.append(sentence)
        if chunk: chunks.append(chunk)
        return chunks
    
    def whisper_long(self,chunks=[], cps=14, overlap=100, output=None, speaker=None):
        global atoks, stoks
        if speaker is None:
            speaker = self.tts.default_speaker 
        elif isinstance(speaker, (str, Path)): 
            speaker = self.tts.extract_spk_emb(speaker)
        r = []
        old_stoks = None
        old_atoks = None
        for i, chunk in enumerate(chunks):
            if self.config.debug: print(f"processing chunk {i+1} of {len(chunks)}:\n{chunk}\n--------------------------\n")
            stoks = self.tts.t2s.generate(chunk, cps=cps, show_progress_bar=False)[0]
            stoks = stoks[stoks != 512]
            if old_stoks is not None:
                #assert(len(stoks) < 750-overlap) # TODO
                stoks = torch.cat([old_stoks[-overlap:], stoks])
                atoks_prompt = old_atoks[:,:,-overlap*3:]
            else:
                atoks_prompt = None
            atoks = self.tts.s2a.generate(stoks, atoks_prompt=atoks_prompt, speakers=speaker.unsqueeze(0), show_progress_bar=False)
            if atoks_prompt is not None: atoks = atoks[:,:,overlap*3+1:]
            r.append(atoks)
            old_stoks = stoks
            old_atoks = atoks
            self.tts.vocoder.decode_to_notebook(atoks)
        audios = []
        for i,atoks in enumerate(r):
            if i != 0: audios.append(torch.zeros((1, int(24000*0.5)), dtype=atoks.dtype, device=atoks.device))
            audios.append(self.tts.vocoder.decode(atoks))
        if output:
            torchaudio.save(output, torch.cat(audios, -1).cpu(), 24000)
