"""generate audio using whisperspeech model"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
try:
    from warnings import simplefilter  # disable coqui future warnings
    simplefilter(action='ignore', category=FutureWarning)
    from contextlib import redirect_stdout, redirect_stderr
    from nltk import sent_tokenize
    from glob import glob
    from os import path, environ as env
    import torch
    import torchaudio
    import re
    from pathlib import Path
    from torch import cuda
    from torch.backends import mps
    from transformers import pytorch_utils
    from whisperspeech.pipeline import Pipeline
    import io
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

# ttspod modules
from ..logger import Logger
from ..util import patched_isin_mps_friendly


class Whisper:
    """whisper text to speech generator"""

    def __init__(self, config=None, log=None, t2s_model=None, s2a_model=None, voice=None):
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.voice = None
        if cuda.is_available():
            self.cpu = 'cuda'
        elif mps.is_available():
            self.cpu = 'mps'
            env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
            pytorch_utils.isin_mps_friendly = patched_isin_mps_friendly
        else:
            self.cpu = 'cpu'
        if not config:
            c = {}
        else:
            if not isinstance(config, dict):
                c = vars(config)
            else:
                c = config
        t2s_model = c.get(
            'whisper_t2s_model', 'whisperspeech/whisperspeech:t2s-base-en+pl.model')
        s2a_model = c.get(
            'whisper_a2s_model', 'whisperspeech/whisperspeech:s2a-q4-base-en+pl.model')
        voice = path.expanduser(voice if voice else c.get('voice', ''))
        if path.isfile(voice):
            self.voice = voice
        elif path.isdir(voice):
            audio_files = glob(path.join(voice, "*wav"))+glob(path.join(voice, "*mp3"))
            if audio_files:
                self.voice = audio_files[0]
        self.tts = Pipeline(t2s_ref=t2s_model,
                            s2a_ref=s2a_model,
                            device=self.cpu,
                            torch_compile=False,
                            optimize=True)

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
            self.log.write('using default speaker')
            speaker = self.tts.default_speaker
        elif isinstance(speaker, (str, Path)):
            self.log.write(f'extracting speaker {speaker}')
            speaker = self.tts.extract_spk_emb(speaker)
        r = []
        old_stoks = None
        old_atoks = None
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        for i, chunk in enumerate(chunks):
            self.log.write(
                f"processing chunk {i+1} of {len(chunks)}\n"
                "--------------------------\n"
                f"{chunk}\n"
                "--------------------------\n")
            try:
                with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
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
        return stdout_buffer.getvalue()+"\n"+stderr_buffer.getvalue()

    def convert(self, text, output_file):
        """convert text input to given output_file"""
        chunks = self.split_and_prepare_text(text)
        try:
            results = self.whisper_long(
                chunks=chunks, output=output_file, speaker=self.voice)
            if results:
                self.log.write(
                    f'TTS conversion complete: {results}')
                return True
            else:
                return False
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(f'TTS conversion failed: {err}', True)
            return False


if __name__ == "__main__":
    whisper = Whisper()
