from pypandoc import convert_text
from html import unescape
import re

platform=None
try:
    import posix_ipc
    platform='unix'
except ImportError:
    pass
try:
    import win32event
    platform='windows'
except ImportError:
    pass

def getLock(name='ttspod',timeout=5):
    global platform
    locked = False
    match platform:
        case 'unix':
            sem = posix_ipc.Semaphore(f"/{name}", posix_ipc.O_CREAT, initial_value=1)
            try:
                sem.acquire(timeout=timeout)
                locked = True
            except:
                pass
        case 'windows':
            sem=win32event.CreateSemaphore(None, 1, 1, "ttspod")
            try:
                result = win32event.WaitForSingleObject(sem, timeout*1000)
                locked = True if result==0 else False
            except:
                pass
    return locked

def releaseLock(name='ttspod',timeout=5):
    global platform
    match platform:
        case 'unix':
            try:
                sem = posix_ipc.Semaphore(f"/{name}")
                sem.release()
            except:
                pass
        case 'windows':
            try:
                sem=win32event.CreateSemaphore(None, 1, 1, "ttspod")
                win32event.ReleaseSemaphore(sem, 1)
            except:
                pass
    return True

def cleanHTML(rawhtml):
    text = convert_text(
            rawhtml,
            'plain',
            format='html',
            extra_args=['--wrap=none', '--strip-comments']
            )
    text = cleanText(text)
    return text

def cleanText(text):
    try:
        text = unescape(text)
        text = re.sub(r'https?:[^ ]*','',text)
        text = text.replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2018',"'").replace(u'\u2019',"'").replace(u'\u00a0',' ')
        text = re.sub(r'[^A-Za-z0-9 \n\/\(\)_.,!"\']',' ',text)
        text = re.sub(r'^ *$','\n',text,flags = re.MULTILINE)
        text = re.sub(r'\n\n+','\n\n',text)
        text = re.sub(r' +',' ',text)
        text = text.strip()
    except:
        pass
    return text
