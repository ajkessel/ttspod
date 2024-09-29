"""main TTS processor"""
# standard modules
try:
    from anyascii import anyascii
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from platform import processor
    from pydub import AudioSegment
    from sys import maxsize
    from traceback import format_exc
    import os
    import re
    import textwrap
    import unicodedata
    import uuid
    import warnings
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# TTSPod modules
from .logger import Logger

# optional modules
try:
    import nltk
    from nltk.tokenize import sent_tokenize, BlanklineTokenizer
except ImportError:
    pass
CPU = 'cpu'
try:
    from torch import cuda
    if cuda.is_available():
        CPU = 'cuda'
except ImportError:
    pass
try:
    from torch.backends import mps
    if mps.is_available():
        if processor() == 'arm':
            CPU = 'mps'
        else:
            CPU = 'cpu'
        # TODO: mps does not appear to work with coqui on i386
except ImportError:
    pass
ENGINES = {}
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import save
    ENGINES['eleven'] = True
except ImportError:
    pass
try:
    from whisperspeech.pipeline import Pipeline
    import torch
    import torchaudio
    warnings.filterwarnings("ignore")  # to suppress TTS output
    ENGINES['whisper'] = True
except ImportError:
    pass
try:
    from TTS.api import TTS
    ENGINES['coqui'] = True
except ImportError:
    pass
try:
    from openai import OpenAI
    # necessary for OpenAI TTS streaming
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    ENGINES['openai'] = True
except ImportError:
    pass


class Speech(object):
    """main TTS processor"""
    def __init__(self, config, dry=False, log=None):
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.config.nltk = False
        self.final_path = config.final_path
        self.dry = dry
        if dry:
            return
        match self.config.engine:
            case "openai":
                self.tts = OpenAI(api_key=self.config.openai_api_key)
            case "eleven":
                self.tts = ElevenLabs(api_key=self.config.eleven_api_key)
            case "whisper":
                self.tts = Pipeline(t2s_ref=self.config.whisper_t2s_model,
                                    s2a_ref=self.config.whisper_s2a_model,
                                    device=CPU, optimize=True)
            case "coqui":
                self.tts = TTS(model_name=self.config.coqui_model,
                               progress_bar=False).to(CPU)
            case _:
                raise ValueError('TTS engine not configured')
        try:
            nltk.data.find('tokenizers/punkt_tab')
            self.config.nltk = True
            self.log.write("nltk found and activated")
        except LookupError:
            try:
                nltk.download('punkt_tab')
                self.config.nltk = True
            except Exception:  # pylint: disable=broad-except
                self.log.write("nltk loading failed")

    def slugify(self, value):
        """convert an arbitrary string to a valid filename"""
        value = str(value)
        value = unicodedata.normalize('NFKD', value).encode(
            'ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value.lower())
        return re.sub(r'[-\s]+', '-', value).strip('-_')

    def speechify(self, title="missing", raw_text=""):
        """workhorse TTS function"""
        clean_title = self.slugify(title)
        out_file = os.path.join(self.config.final_path, f'{clean_title}.mp3')
        text = anyascii(raw_text)
        temp = str(uuid.uuid4())

        if os.path.exists(out_file):
            out_file = os.path.join(
                self.config.final_path, f'{clean_title}-{temp}.mp3')

        if self.dry:
            self.log.write(f'dry run: not creating {out_file}')
            return

        if self.config.engine == "whisper":
            chunks = self.split_and_prepare_text(text)
            self.whisper_long(chunks=chunks, output=out_file,
                              speaker=self.config.whisper_voice)
            os.chmod(out_file, 0o644)
            return out_file

        if self.config.nltk:
            paragraphs = BlanklineTokenizer().tokenize(text)
        else:
            paragraphs = text.split('\n\n')
        segments = []
        if self.config.engine == 'coqui':
            max_length = 250
        else:
            max_length = 4096

        for para in paragraphs:
            self.log.write(f"paragraph {para}")
            if len(para) < 8:  # skip very short lines which are likely not text
                continue
            if len(para) > max_length:  # break overlong paras into sentences
                self.log.write(
                    f"further splitting paragraph of length {len(para)}")
                if self.config.nltk:
                    sentences = sent_tokenize(para)
                else:
                    sentences = textwrap.wrap(text=para, width=max_length)
                for sentence in sentences:
                    # break sentences greater than 4096 characters into smaller pieces
                    if len(sentence) > max_length:
                        chunks = textwrap.wrap(text=sentence, width=max_length)
                        for chunk in chunks:
                            if len(chunk) < max_length:
                                segments.append(chunk)
                            else:  # if we can't find a small enough piece, we give up
                                self.log.write(
                                    "abnormal sentence fragment found, skipping")
                    else:
                        segments.append(sentence)
            else:
                segments.append(para)
        if self.config.engine == "coqui":
            try:
                combined = AudioSegment.empty()
                for (i, segment) in enumerate(segments):
                    segment_audio = os.path.join(
                        self.config.temp_path, f'{clean_title}-{i}.wav')
                    # pylint: disable=no-member
                    self.tts.tts_to_file(
                        text=segment,
                        speaker=self.config.coqui_speaker,
                        language=self.config.coqui_language,
                        file_path=segment_audio
                    )
                    # pylint: enable=no-member
                    combined += AudioSegment.from_file(segment_audio)
                combined.export(out_file, format="mp3")
                if os.path.isfile(out_file):
                    os.chmod(out_file, 0o644)
            except Exception as err:  # pylint: disable=broad-except
                self.log.write(
                    f'TTS engine {self.config.engine} failed: {err}\n'+format_exc())
            return out_file if os.path.isfile(out_file) else None
        try:
            if self.config.engine == "openai":
                def tts_function(z):
                    return self.tts.audio.speech.create(
                        model=self.config.openai_model,
                        voice=self.config.openai_voice,
                        input=z
                    )
            elif self.config.engine == "eleven":
                def tts_function(z):
                    return self.tts.generate(
                        voice=self.config.eleven_voice,
                        model=self.config.eleven_model,
                        text=z
                    )
            else:
                raise ValueError("No TTS engine configured.")
            futures = []
            # TODO - use these hashes to see if any segment has already been transcribed
            self.log.write(f'processing {len(segments)} segments')
            hashes = [str(hash(segment) % ((maxsize + 1) * 2))
                      for segment in segments]
            combined = AudioSegment.empty()
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                for future in executor.map(tts_function, segments):
                    futures.append(future)
                for i, future in enumerate(futures):
                    segment_audio = os.path.join(
                        self.config.temp_path,
                        f'{clean_title}-{hashes[i]}.mp3'
                    )
                    if self.config.engine == "openai":
                        future.stream_to_file(segment_audio)
                    elif self.config.engine == "eleven":
                        save(future, segment_audio)
                    combined += AudioSegment.from_mp3(segment_audio)
                combined.export(out_file, format="mp3")
                if os.path.isfile(out_file):
                    os.chmod(out_file, 0o644)
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(
                f'TTS engine {self.config.engine} failed: {err}\n'+format_exc()
            )
        return out_file if os.path.isfile(out_file) else None

    def split_and_prepare_text(self, text, cps=14):
        """break text into chunks for whisperspeech"""
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
        if chunk:
            chunks.append(chunk)
        return chunks

    def whisper_long(self, chunks=None, cps=14, overlap=100, output=None, speaker=None):
        """main whisperspeech generator"""
        if not speaker:
            speaker = self.tts.default_speaker
        elif isinstance(speaker, (str, Path)):
            speaker = self.tts.extract_spk_emb(speaker)
        r = []
        old_stoks = None
        old_atoks = None
        for i, chunk in enumerate(chunks):
            self.log.write(
                f"processing chunk {i+1} of {len(chunks)}\n"
                "--------------------------\n"
                f"{chunk}\n"
                "--------------------------\n")
            try:
                stoks = self.tts.t2s.generate(
                    chunk, cps=cps, show_progress_bar=False)[0]
                stoks = stoks[stoks != 512]
                if old_stoks is not None:
                    assert len(stoks) < 750-overlap  # TODO
                    stoks = torch.cat([old_stoks[-overlap:], stoks])
                    atoks_prompt = old_atoks[:, :, -overlap*3:]
                else:
                    atoks_prompt = None
                atoks = self.tts.s2a.generate(
                    stoks,
                    atoks_prompt=atoks_prompt,
                    speakers=speaker.unsqueeze(0),
                    show_progress_bar=False
                )
                if atoks_prompt is not None:
                    atoks = atoks[:, :, overlap*3+1:]
                r.append(atoks)
                self.tts.vocoder.decode_to_notebook(atoks)
            except Exception as err:  # pylint: disable=broad-except
                self.log.write(f'chunk {i+1} failed with error {err}')
            old_stoks = stoks
            old_atoks = atoks
        audios = []
        for i, atoks in enumerate(r):
            if i != 0:
                audios.append(torch.zeros((1, int(24000*0.5)),
                              dtype=atoks.dtype, device=atoks.device))
            audios.append(self.tts.vocoder.decode(atoks))
        if output:
            torchaudio.save(output, torch.cat(audios, -1).cpu(), 24000)
