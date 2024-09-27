try:
    from pypandoc import convert_text
    from html import unescape
    import re
except Exception as e:
    print(f'Failed to import required module: {e}\nDo you need to run pip install -r requirements.txt?')
    exit()

platform=None
try:
    import posix_ipc
    platform='unix'
except ImportError:
    pass
try:
    from semaphore_win_ctypes import Semaphore
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
            sem = Semaphore(name)
            try:
                sem.open()
                result = sem.acquire(timeout_ms = timeout*1000)
                locked = True if result else False
            except:
                try:
                    sem.create(maximum_count = 1)
                    result = sem.acquire(timeout_ms = timeout*1000)
                    locked = True if result else False
                except:
                    pass
    return locked

def releaseLock(name='ttspod',timeout=5):
    global platform
    released = False
    match platform:
        case 'unix':
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
