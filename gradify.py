import numpy as np
import os
from grad_tts.model import GradTTS, params
import torch
from grad_tts.text.symbols import symbols
from grad_tts.text import text_to_sequence, cmudict
from grad_tts.utils import intersperse
from scipy.io.wavfile import write
from grad_tts.model.hifi_gan.models import Generator as HiFiGAN
from pydub import AudioSegment

class Gradify(object):
    def __init__(self, grad, hifigan):
        self.generator = GradTTS(len(symbols) + 1, params.n_spks, params.spk_emb_dim,
                            params.n_enc_channels, params.filter_channels,
                            params.filter_channels_dp, params.n_heads, params.n_enc_layers,
                            params.enc_kernel, params.enc_dropout, params.window_size,
                            params.n_feats, params.dec_dim, params.beta_min, params.beta_max, params.pe_scale)
        self.generator.load_state_dict(torch.load(grad, map_location=lambda loc, storage: loc))
        _ = self. generator.eval()
        self.cmu = cmudict.CMUDict()
        self.vocoder = HiFiGAN()
        self.vocoder.load_state_dict(torch.load(hifigan, map_location=lambda loc, storage: loc)['generator'])
        _ = self.vocoder.eval()
        self.vocoder.remove_weight_norm()
    def transcribe(self, segment, path = "./out.wav"):
        with torch.no_grad():
            x = torch.LongTensor(intersperse(text_to_sequence(segment, dictionary=self.cmu), len(symbols)))[None]
            x_lengths = torch.LongTensor([x.shape[-1]])
            y_enc, y_dec, attn = self.generator.forward(x, x_lengths, n_timesteps=10, temperature=1.5,
                                                    stoc=False, spk=None, length_scale=0.91)
            audio = (self.vocoder.forward(y_dec).cpu().squeeze().clamp(-1, 1).numpy() * 32767).astype(np.int16)
            write(f'{path}.wav', 22050, audio)
            AudioSegment.from_wav(f"{path}.wav").export(f"{path}", format="mp3")