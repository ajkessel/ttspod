import os
import unicodedata
import re
import textwrap
import uuid
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
except:
    pass
try:
    from openai import OpenAI
except:
    pass

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
    def speechify(self, title, raw_text):
        out_file = self.config.final_path + self.slugify(title) + ".mp3"
        text = anyascii(raw_text)
        temp = str(uuid.uuid4())
        if os.path.exists(out_file):
            out_file = self.config.final_path + self.slugify(title) + "-" + temp + ".mp3"
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
                elif self.config.engine == 'whisper':
                    self.tts.generate_to_file(segment_audio, segment, speaker=self.config.whisper_voice)
                if self.config.debug: print(f'segment successful')
            except Exception as e:
                if self.config.debug: print(f'TTS failed {e}')
            else:
                combined += AudioSegment.from_mp3(segment_audio)
        try:
            if combined.duration_seconds > 10:
                combined.export(out_file, format="mp3")
                os.chmod(out_file, 0o644)
                return (out_file)
            else:
                return None
        except:
            return None
