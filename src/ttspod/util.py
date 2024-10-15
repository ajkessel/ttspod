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
    from os import path
    from platform import platform
    from pypandoc import convert_text
    from sys import executable
    from unidecode import unidecode
    import re
    import subprocess
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

from . import version

OS = None
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


def get_lock(name='ttspod', timeout=5):
    """attempt to obtain a semaphore for the process"""
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


def release_lock(name='ttspod'):
    """release a previously locked semaphore"""
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
    """convert HTML to plaintext"""
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
    text = re.sub(r'[^A-Za-z0-9% \n\/\(\)_.,!"\']', ' ', text)
    text = re.sub(r'^ *$', '\n', text, flags=re.MULTILINE)
    text = re.sub(r'\n\n+', '\n\n', text)
    text = re.sub(r' +', ' ', text)
    text = unidecode(text.strip())
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

    def upgrade(force=False, debug=False):
        """upgrade ttspod in place"""
        current_version = version.__version__
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
            print('Installing customized transformers module for Mac...')
            result = subprocess.run(
                [executable, "-m", "pip", "install",
                 "git+https://github.com/ajkessel/transformers@v4.42.4a", "-U"],
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
        new_version = version.__version__
        if current_version != new_version:
            print(f'Upgraded from {current_version} to {new_version}.')
        else:
            print(f'Version unchanged ({current_version}).')

# pylint: enable=c-extension-no-member
