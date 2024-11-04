"""general purpose utility functions"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

try:
    from html import unescape
    from html2text import html2text
    from importlib import reload
    from importlib.util import find_spec
    import spacy
    import enchant
    from os import path
    from platform import platform
    from pypandoc import convert_text
    from sys import executable
    # from textwrap import wrap
    from unidecode import unidecode
    import re
    import subprocess
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

import version

OS = None
DICTIONARY = enchant.Dict("en_US")

my_platform = platform().lower()
if "windows" in my_platform:
    try:
        from semaphore_win_ctypes import Semaphore
        OS = 'windows'
    except ImportError:
        pass
elif "macos" in my_platform:
    try:
        import posix_ipc
        OS = 'mac'
    except ImportError:
        pass
else:
    try:
        import posix_ipc
        OS = 'unix'
    except ImportError:
        pass

# pylint: disable=bare-except
# pylint: disable=c-extension-no-member


def check_engines() -> dict:
    """try importing various TTS modules to determine what is available"""
    # optional modules - disable linting since we are checking if modules exist
    # pylint: disable=unused-import,invalid-name,import-outside-toplevel
    ENGINES = {}
    try:
        from elevenlabs.client import ElevenLabs
        from elevenlabs import save
        ENGINES['eleven'] = True
    except ImportError:
        pass
    try:
        from whisperspeech.pipeline import Pipeline
        ENGINES['whisper'] = True
    except ImportError:
        pass
    try:
        from f5_tts.infer.utils_infer import load_checkpoint
        ENGINES['f5'] = True
    except ImportError:
        pass
    try:
        from TTS.api import TTS
        ENGINES['coqui'] = True
    except ImportError:
        pass
    try:
        from openai import OpenAI
        ENGINES['openai'] = True
    except ImportError:
        pass
    # pylint: enable=unused-import
    return ENGINES


def get_spacy():
    """retrieve model for spacy tokenizer"""
    nlp = None
    if not spacy.util.is_package("en_core_web_lg"):
        spacy.cli.download("en_core_web_lg")
    nlp = spacy.load("en_core_web_lg")
    nlp.add_pipe('sentencizer')
    return nlp


def chunk(text=None, min_length=0, max_length=250) -> list[str]:
    """
    chunk text into segments for speechifying

    :param text: text to split into chunks
    :param max_length: maximum length of each chunk
    """
    assert min_length < max_length, \
        "Invalid arguments given to chunk function:" \
        "minimum {min_length} is greater than maximum {max_length}."

    # TODO: add extra silence for paragraph breaks
    text = re.sub(r'([^\.])\n\n', r'\1. ', text)
    text = re.sub(r' +\. +', '. ', text)
    text = re.sub(r'[ \n]+', ' ', text)
    text = text.strip()
    nlp = get_spacy()
    doc = nlp(text)
    sentences = [sent.text.strip() for sent in doc.sents]
    if not sentences:
        return []
    chunks = []
    sentence = sentences[0]
    next_sentence = ''
    if len(sentences) > 1:
        sentences = sentences[1:]
        for next_sentence in sentences:
            if re.match(r'^ *[A-Za-z\.]{,3} *$', next_sentence):
                continue
            if len(sentence) + len(next_sentence) <= min_length:
                sentence += f' {next_sentence}'
                continue
            if len(sentence) <= max_length:
                chunks.append(sentence)
                sentence = next_sentence
                continue
            # fragments = re.findall(r'[^,;\.\-\?]+[,;\.\-\?](?!\d)', sentence)
            fragments = re.split(r'(?<=[,.:?])(?!\w)', sentence)
            fragment = ''
            for next_fragment in fragments:
                next_fragment = next_fragment.strip()
                if len(next_fragment) < 10 or len(fragment) + len(next_fragment) <= max_length:
                    fragment += next_fragment
                    continue
                if len(fragment) <= max_length:
                    chunks.append(fragment)
                    fragment = next_fragment
                    continue
                chunks.append(fragment)
                fragment = next_fragment
                # lines = wrap(text=fragment, width=max_length) TODO: extra long fragments
                # chunks.extend(lines)
            chunks.append(fragment)
            sentence = next_sentence
        chunks.append(sentence)
    chunks = [x for x in chunks if len(x.strip()) > 0]
    return chunks


def get_lock(name='ttspod', timeout=5) -> bool:
    """
    attempt to obtain a semaphore for the process

    :param name: name of semaphore
    :param timeout: how long to wait for semaphore in seconds
    """
    locked = False
    match OS:
        case 'unix':
            sem = posix_ipc.Semaphore(  # pylint: disable=E0606
                f"/{name}", posix_ipc.O_CREAT, initial_value=1)
            try:
                sem.acquire(timeout=timeout)
                locked = True
            except:
                pass
        case 'mac':  # semaphore timeout doesn't work on Mac
            sem = posix_ipc.Semaphore(
                f"/{name}", posix_ipc.O_CREAT, initial_value=1)
            try:
                sem.acquire(timeout=0)
                locked = True
            except:
                pass
        case 'windows':
            sem = Semaphore(name)  # pylint: disable=E0606
            try:
                sem.open()
                result = sem.acquire(timeout_ms=timeout*1000)
                locked = True if result else False
            except:
                try:
                    sem.create(maximum_count=1)
                    result = sem.acquire(timeout_ms=timeout*1000)
                    locked = True if result else False
                except:
                    pass
        case _:
            locked = True
    return locked


def release_lock(name='ttspod') -> bool:
    """
    release a previously locked semaphore

    :param name: name of semaphore to release
    """
    released = False
    match OS:
        case 'unix':
            try:
                sem = posix_ipc.Semaphore(f"/{name}")
                sem.release()
                released = True
            except:
                pass
        case 'mac':
            try:
                sem = posix_ipc.Semaphore(f"/{name}")
                sem.release()
                released = True
            except:
                pass
        case 'windows':
            try:
                sem = Semaphore(name)
                sem.open()
                sem.release()
                sem.close()
                released = True
            except:
                pass
        case _:
            released = True
    return released
# pylint: enable=bare-except


def clean_html(raw_html):
    """
    convert HTML to plaintext
    
    :param raw_html: unprocessed HTML content to strip of tags and other cruft
    """
    text = None
    try:
        text = convert_text(
            raw_html,
            'plain',
            format='html',
            extra_args=['--wrap=none', '--strip-comments']
        )
    except Exception:  # pylint: disable=broad-except
        pass
    if not text:
        try:
            text = html2text(raw_html)
        except Exception:  # pylint: disable=broad-except
            pass
    if text:
        text = clean_text(text)
        return text
    else:
        return ""


def fix_path(text, trail=False):
    """standardize a directory path and expand ~"""
    try:
        fixed_text = path.expanduser(text).replace('\\', '/')
        if trail:
            fixed_text = path.join(fixed_text, '')
    except Exception:  # pylint: disable=broad-except
        fixed_text = text
    return fixed_text


def clean_text(text):
    """remove as much non-speakable text as possible"""
    text = unescape(text)
    text = re.sub(r'https?:[^ ]*', '', text)
    text = re.sub(r'mailto:[^ ]*', '', text)
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace(
        '\u2018', "'").replace('\u2019', "'").replace('\u00a0', ' ')
    text = re.sub(r'[^A-Za-z0-9% \n\/\(\)_.,!"\'\?\:]', ' ', text)
    text = re.sub(r'^ *$', '\n', text, flags=re.MULTILINE)
    text = re.sub(r'\n\n+', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    text = unidecode(text.strip())
    all_caps_words = re.findall(r'[A-Z]{2,15}', text)
    try:
        for word in all_caps_words:
            if DICTIONARY.check(word):
                replacement = word.lower()
                text = text.replace(word, replacement)
    except Exception:  # pylint: disable=broad-except
        pass
    return text


# If Windows getch() available, use that.  If not, use a
# Unix version.
try:
    import msvcrt
    get_character = msvcrt.getch
except ImportError:
    import sys
    import tty
    import termios

    def _unix_getch():
        """Get a single character from stdin, Unix version"""

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())          # Raw read
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    get_character = _unix_getch


def patched_isin_mps_friendly(elements, test_elements):
    """hack to enable mps GPU support for Mac TTS"""
    if test_elements.ndim == 0:
        test_elements = test_elements.unsqueeze(0)
    return elements.tile(
        test_elements.shape[0], 1).eq(test_elements.unsqueeze(1)).sum(dim=0).bool().squeeze()


def upgrade(force=False, debug=False) -> bool:
    """upgrade ttspod in place"""
    current_version = version.__version__
    try:
        options = []
        if find_spec('openai'):
            options.append('remote')
        if find_spec('TTS.api'):
            options.append('local')
        if find_spec('truststore'):
            options.append('truststore')
        if find_spec('twine'):
            options.append('dev')
        if options:
            option_string = re.sub(r"[' ]", '', str(options))
        else:
            option_string = ""
        print(f'Upgrading in place with options {option_string}...')
        if not force:
            print(' (include -f to force re-installation) ')
        results = b''
        result = subprocess.run(
            [executable, "-m", "pip", "cache", "remove", "ttspod"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        results += result.stdout + result.stderr
        installer = [executable, "-m", "pip",
                     "install", f"ttspod{option_string}", "-U"]
        if force:
            installer.append("--force-reinstall")
        result = subprocess.run(
            installer,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        results += result.stdout + result.stderr
        if OS == "mac" and 'local' in options:
            print('Installing customized transformers module for Mac github...')
            result = subprocess.run(
                [executable, "-m", "pip", "install",
                 "git+https://github.com/ajkessel/transformers@v4.42.4a", "-U"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False
            )
            results += result.stdout + result.stderr
        print('Installing customized F5-TTS module from github...')
        result = subprocess.run(
            [executable, "-m", "pip", "install",
                "git+https://github.com/SWivid/F5-TTS", "-U"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        results += result.stdout + result.stderr
        results = results.decode('utf-8')
        lines = [x for x in results.splitlines() if x.strip() and
                 not "cache is disabled" in x.lower() and
                 ("warning" in x.lower() or "error" in x.lower())]
        if debug:
            print(results)
        elif lines:
            print('Errors/warnings in upgrade:\n')
            for line in lines:
                print(f'{line}\n')
        reload(version)
    except Exception as err:  # pylint: disable=broad-except
        print(f'Error occurred: {err}')
    new_version = version.__version__
    if current_version != new_version:
        print(f'Upgraded from {current_version} to {new_version}.')
        return True
    else:
        print(f'Version unchanged ({current_version}).')
        return False

# pylint: enable=c-extension-no-member


if __name__ == '__main__':
    print("This is the TTSPod util module. "
          "It is not intended to run separately except for debugging.")
