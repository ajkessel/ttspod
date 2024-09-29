"""general purpose utility functions"""
try:
    from pypandoc import convert_text
    from html import unescape
    from html2text import html2text
    from unidecode import unidecode
    from platform import platform
    import re
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'Do you need to run pip install -r requirements.txt?')
    exit()

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
            sem = posix_ipc.Semaphore(
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
            sem = Semaphore(name)
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
    import sys, tty, termios
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

# pylint: enable=c-extension-no-member
