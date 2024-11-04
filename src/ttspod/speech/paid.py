"""generate audio using coqui model"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from concurrent.futures import ThreadPoolExecutor
    from nltk.tokenize import BlanklineTokenizer
    from pydub import AudioSegment
    from sys import maxsize
    from traceback import format_exc
    import os
    import textwrap
    import warnings
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# optional modules
try:
    from openai import OpenAI
    # necessary for OpenAI TTS streaming
    warnings.filterwarnings("ignore", category=DeprecationWarning)
except ImportError:
    pass
try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import save
except ImportError:
    pass

# ttspod modules
from logger import Logger
from util import get_spacy

MAX_LENGTH = 4096  # hardcoded maximum value for API-based TTS
OPENAI_MODEL = 'tts-1'
OPENAI_VOICE = 'nova'
ELEVEN_MODEL = 'eleven_monolingual_v1'
ELEVEN_VOICE = 'Daniel'
MAX_WORKERS = 10

class Paid:
    """text to OpenAI or Eleven"""

    def __init__(self, config=None, log=None, engine=None,
                 openai_key=None, eleven_key=None,
                 max_workers=None, openai_model=None,
                 openai_voice=None, eleven_model=None,
                 eleven_voice=None, temp_path=None):
        self.log = log if log else Logger(debug=True)
        if isinstance(config,dict):
            self.c = config
        elif config:
            self.c = vars(config)
        else:
            self.c = { }
        self.nlp = get_spacy()
        self.engine = engine if engine else self.c.get('engine','')
        self.oai_key = openai_key if openai_key else self.c.get('openai_api_key','')
        self.el_key = eleven_key if eleven_key else self.c.get('eleven_api_key','')
        self.oai_model = openai_model if openai_model else self.c.get('openai_model',OPENAI_MODEL)
        self.oai_voice = openai_voice if openai_voice else self.c.get('openai_voice',OPENAI_VOICE)
        self.el_model = eleven_model if eleven_model else self.c.get('eleven_model',ELEVEN_MODEL)
        self.el_voice = eleven_voice if eleven_voice else self.c.get('eleven_voice',ELEVEN_VOICE)
        self.max_workers = max_workers if max_workers else self.c.get('max_workers',MAX_WORKERS)
        self.temp_path = os.path.join(temp_path if temp_path else self.c.get('temp_path','.'),'')
        match self.engine.lower():
            case "openai":
                self.tts = OpenAI(api_key=self.oai_key)
            case "eleven":
                self.tts = ElevenLabs(api_key=self.el_key)
            case _:
                self.tts = None
                self.log.write(f'no valid paid TTS engine specified: {self.engine}')

    def segmentize(self, text):
        """ break arbitrary input text of segments of MAX_LENGTH or less"""
        try:
            paragraphs = BlanklineTokenizer().tokenize(text)
        except Exception: # pylint: disable=broad-except
            paragraphs = text.split('\n\n')
        segments = []

        for para in paragraphs:
            self.log.write(f"paragraph {para}")
            if len(para) < 8:  # skip very short lines which are likely not text
                continue
            if len(para) > MAX_LENGTH:  # break overlong paras into sentences
                self.log.write(
                    f"further splitting paragraph of length {len(para)}")
                sentences = []
                try:
                    doc = self.nlp(para)
                    sentences = [sent.text.strip() for sent in doc.sents]
                except Exception:  # pylint: disable=broad-except
                    pass
                if not sentences:  # fallback method, simple line wrap
                    sentences = textwrap.wrap(text=para, width=MAX_LENGTH)
                for sentence in sentences:
                    # break sentences greater than 4096 characters into smaller pieces
                    if len(sentence) > MAX_LENGTH:
                        chunks = textwrap.wrap(text=sentence, width=MAX_LENGTH)
                        for chunk in chunks:
                            if len(chunk) < MAX_LENGTH:
                                segments.append(chunk)
                            else:  # if we can't find a small enough piece, we give up
                                self.log.write(
                                    "abnormal sentence fragment found, skipping")
                    else:
                        segments.append(sentence)
            else:
                segments.append(para)
        return segments

    def convert(self, text, output_file):
        """convert text input to given output_file"""

        segments = self.segmentize(text)

        try:
            if self.engine == "openai":
                def tts_function(z):
                    return self.tts.audio.speech.create(
                        model=self.oai_model,
                        voice=self.oai_voice,
                        input=z
                    )
            elif self.engine == "eleven":
                def tts_function(z):
                    return self.tts.generate(
                        voice=self.el_voice,
                        model=self.el_model,
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
            temp_base = os.path.splitext(os.path.basename(output_file))[0]
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                for future in executor.map(tts_function, segments):
                    futures.append(future)
                for i, future in enumerate(futures):
                    segment_audio = os.path.join(
                        self.temp_path,
                        f'{temp_base}-{hashes[i]}.mp3'
                    )
                    if self.engine == "openai":
                        future.stream_to_file(segment_audio)
                    elif self.engine == "eleven":
                        save(future, segment_audio)
                    combined += AudioSegment.from_mp3(segment_audio)
                combined.export(output_file, format="mp3")
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(
                f'TTS engine {self.engine} failed: {err}\n'+format_exc()
            )
        return True if os.path.isfile(output_file) else False

if __name__ == "__main__":
    paid = Paid()
