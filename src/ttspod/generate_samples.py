"""freestanding script to generate sample audio output"""
# optional system certificate trust
# cspell: disable
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from os import path, getcwd, listdir
    from pathlib import Path
    from shutil import rmtree
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# TTSPod modules
from speech import speech

TEXT = """
    The quick brown fox jumped over the lazy dog. The dog was so lazy, he did not even notice that the fox was brown.
    Have you ever seen a blue fox? I have not!
    """


class Config(object):
    """simplified config option for generating speech samples"""

    def __init__(self):
        self.engine = "coqui"
        self.nltk = True
        self.log = None
        self.gpu = 1
        self.tortoise_path = path.join(
            getcwd(), 'examples/voices/tortoise/', '')
        self.xtts_path = path.join(getcwd(), 'examples/voices/xtts', '')
        self.final_path = None
        self.model = None
        self.voice = None


def main():
    """generate sample TTS files"""

    c = Config()
    for p in [c.tortoise_path, c.xtts_path]:
        if path.exists(p):
            print(f'Output folder {p} already exists.\n')
            remove_question = input('Remove and recreate? (y/n)')
            if remove_question.lower() == "y":
                rmtree(p)

    c.final_path = c.tortoise_path
    c.model = "tortoise"
    Path(c.final_path).mkdir(parents=True, exist_ok=True)

    voice_path = path.join(getcwd(), 'working/voices', '')
    if not path.isdir(voice_path):
        print(f'{voice_path} does not exist.\n')
        path_question = input('Enter path for voice samples to generate:')
        voice_path = path.join(path.expanduser(path_question), '')
        if not path.isdir(voice_path):
            print(f'Cannot find path {voice_path}. Exiting.')
            exit()

    voices = listdir(voice_path)
    voices.sort()

    print(f'sample text:\n{TEXT}')
    for voice in voices:
        try:
            print(f'generating sample {voice}')
            c.voice = path.join(voice_path, voice, '')
            tts = speech.Speech(config=c)
            fullpath = tts.speechify(
                title=voice, raw_text=TEXT, overwrite=False)
            print(f'output to: {fullpath}')
            del tts
        except Exception as err:  # pylint: disable=broad-except
            print(f'failed with {err}\n')

    c.final_path = c.xtts_path
    c.model = "xtts"
    Path(c.final_path).mkdir(parents=True, exist_ok=True)

    voices = [
        'Claribel Dervla', 'Daisy Studious', 'Gracie Wise', 'Tammie Ema', 'Alison Dietlinde',
        'Ana Florence', 'Annmarie Nele', 'Asya Anara', 'Brenda Stern', 'Gitta Nikolina',
        'Henriette Usha', 'Sofia Hellen', 'Tammy Grit', 'Tanja Adelina', 'Vjollca Johnnie',
        'Andrew Chipper', 'Badr Odhiambo', 'Dionisio Schuyler', 'Royston Min', 'Viktor Eka',
        'Abrahan Mack', 'Adde Michal', 'Baldur Sanjin', 'Craig Gutsy', 'Damien Black',
        'Gilberto Mathias', 'Ilkin Urbano', 'Kazuhiko Atallah', 'Ludvig Milivoj', 'Suad Qasim',
        'Torcull Diarmuid', 'Viktor Menelaos', 'Zacharie Aimilios', 'Nova Hogarth', 'Maja Ruoho',
        'Uta Obando', 'Lidiya Szekeres', 'Chandra MacFarland', 'Szofi Granger',
        'Camilla Holmström', 'Lilya Stainthorpe', 'Zofija Kendrick', 'Narelle Moon',
        'Barbora MacLean', 'Alexandra Hisakawa', 'Alma María', 'Rosemary Okafor',
        'Ige Behringer', 'Filip Traverse', 'Damjan Chapman', 'Wulf Carlevaro', 'Aaron Dreschner',
        'Kumar Dahl', 'Eugenio Mataracı', 'Ferran Simen', 'Xavier Hayasaka', 'Luis Moray',
        'Marcos Rudaski'
    ]

    for voice in voices:
        try:
            print(f'generating sample {voice}')
            c.voice = voice
            tts = speech.Speech(config=c)
            fullpath = tts.speechify(voice, TEXT)
            del tts
        except Exception as err:  # pylint: disable=broad-except
            print(f'failed with {err}\n')


if __name__ == "__main__":
    main()
