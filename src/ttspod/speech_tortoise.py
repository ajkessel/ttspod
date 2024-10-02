"""generate TTS using tortoise engine"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
from platform import processor
from os.path import isfile
import re
import torch
import torchaudio
from tortoise.api import TextToSpeech
from tortoise.utils.audio import load_voice
from transformers import pytorch_utils

# ttspod modules
from .logger import Logger
from .util import patched_isin_mps_friendly

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
        CPU = 'mps'
        pytorch_utils.isin_mps_friendly = patched_isin_mps_friendly
        if processor() == 'arm':
            CPU = 'mps'
        else:
            CPU = 'cpu'
except ImportError:
    pass


class Tortoise(object):
    """Tortoise TTS engine"""

    def __init__(self, config=None, log=None):
        self.log = log if log else Logger(debug=True)
        if not config:
            e = {}
        else:
            e = vars(config)
        self.args = e.get(
            'tortoise_args',
            {
                'use_deepspeed': True,
                'kv_cache': True,
                'half': True,
                'device': CPU
            })
        self.preset = e.get("tortoise_preset", "ultra_fast")
        self.voice = e.get("tortoise_voice", "daniel")
        self.voice_path = e.get("tortoise_voice_path", None)
        self.debug = e.get("debug", False)
        if CPU == 'cuda':
            torch.cuda.empty_cache()
        elif CPU == 'mps':
            pytorch_utils.isin_mps_friendly = patched_isin_mps_friendly
        self.log.write('starting tortoise-tts with settings'
                       f'{self.args} {self.preset} {self.voice} {self.debug}')
        self.tts = TextToSpeech(**self.args)

    def split_and_recombine_text(self, text, desired_length=200, max_length=300):
        """Split text it into chunks of a desired length trying to keep sentences intact."""
        # normalize text, remove redundant whitespace and convert non-ascii quotes to ascii
        text = re.sub(r'\n\n+', '\n', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[“”]', '"', text)

        rv = []
        in_quote = False
        current = ""
        split_pos = []
        pos = -1
        end_pos = len(text) - 1

        def seek(delta):
            nonlocal pos, in_quote, current
            is_neg = delta < 0
            for _ in range(abs(delta)):
                if is_neg:
                    pos -= 1
                    current = current[:-1]
                else:
                    pos += 1
                    current += text[pos]
                if text[pos] == '"':
                    in_quote = not in_quote
            return text[pos]

        def peek(delta):
            p = pos + delta
            return text[p] if p < end_pos and p >= 0 else ""

        def commit():
            nonlocal rv, current, split_pos
            rv.append(current)
            current = ""
            split_pos = []

        while pos < end_pos:
            c = seek(1)
            # do we need to force a split?
            if len(current) >= max_length:
                if len(split_pos) > 0 and len(current) > (desired_length / 2):
                    # we have at least one sentence and we are over half the desired length,
                    # seek back to the last split
                    d = pos - split_pos[-1]
                    seek(-d)
                else:
                    # no full sentences, seek back until we are not in the middle of a word
                    # and split there
                    while c not in '!?.\n ' and pos > 0 and len(current) > desired_length:
                        c = seek(-1)
                commit()
            # check for sentence boundaries
            elif not in_quote and (c in '!?\n' or (c == '.' and peek(1) in '\n ')):
                # seek forward if we have consecutive boundary markers
                # but still within the max length
                while pos < len(text) - 1 and len(current) < max_length and peek(1) in '!?.':
                    c = seek(1)
                split_pos.append(pos)
                if len(current) >= desired_length:
                    commit()
            # treat end of quote as a boundary if its followed by a space or newline
            elif in_quote and peek(1) == '"' and peek(2) in '\n ':
                seek(2)
                split_pos.append(pos)
        rv.append(current)

        # clean up, remove lines with only whitespace or punctuation
        rv = [s.strip() for s in rv]
        rv = [s for s in rv if len(
            s) > 0 and not re.match(r'^[\s\.,;:!?]*$', s)]

        return rv

    def write(self, text=None, output=None, preset=None,
              voice=None, voice_path=None):
        """convert input text to output mp3 file"""

        preset = preset if preset else self.preset
        voice = voice if voice else self.voice
        voice_path = voice_path if voice_path else self.voice_path
        chunks = self.split_and_recombine_text(text)

        try:
            voice_samples, conditioning_latents = load_voice(
                voice=voice, extra_voice_dirs=voice_path)
        except Exception:  # pylint: disable=broad-except
            self.log.write(
                f'could not load voice {voice} from {voice_path}, '
                'trying daniel as default')
            try:
                voice_samples, conditioning_latents = load_voice(
                    voice='daniel')
            except Exception:  # pylint: disable=broad-except
                self.log.write(
                    'could not load any voice files, please reconfigure')
                return None
        audios = []
        for i, chunk in enumerate(chunks):
            print(f'processing chunk {i+1} of {len(chunks)}: {chunk}')
            gen = self.tts.tts_with_preset(chunk, voice_samples=voice_samples,
                                           conditioning_latents=conditioning_latents, preset=preset)
            audio = gen.squeeze(0).cpu()
            audios.append(audio)

        audio = torch.cat(audios, dim=-1)
        torchaudio.save(output, audio, 24000)
        if isfile(output):
            return output
        else:
            self.log.write('something went wrong, no audio generated')
            return None
        
