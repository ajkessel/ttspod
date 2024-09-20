from html import unescape
from html2text import html2text
from lxml import html
from quopri import decodestring
import email
import hashlib
import magic
import pypandoc
import re
import time
import validators
try:
    import trafilatura # to extract readable content from webpages
    trafilatura_available = True
except ImportError:
    trafilatura_available = False

class Content(object):
    def __init__(self, config):
        self.config = config
        pass

    def processEmail(self, text, title = None):
        msg = email.message_from_string(text)
        title_search = msg.get('subject')
        url = msg.get('message-id')
        if title_search:
            title = title_search
        elif not title:
            title = "Untitled Content"
        candidates=[]
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                candidates.append(part.get_payload(decode=True))
            elif part.get_content_type() == 'text/html':
                candidates.append(part.get_payload(decode=True))
        if candidates:
            candidate = max(candidates, key=len)
            if '<html' in str(candidate):
                text = self.cleanHTML(candidate)
            else:
                text = candidate
            entry = ( title, text, url )
            return [ entry ]
        return None

    def cleanHTML(self, rawhtml):
         text = pypandoc.convert_text(
                    rawhtml,
                    'plain',
                    format='html',
                    extra_args=['--wrap=none', '--strip-comments']
                    )
         text = text.encode('ascii', 'ignore').decode('ascii')
         text = text.replace('|', '').replace('-', ' ').replace('+', ' ')
         text = re.sub(r'[^A-Za-z0-9 \n\-_.,!"\']',' ',text)
         text = re.sub(r'^ *$','\n',text,flags = re.MULTILINE)
         text = re.sub(r'\n\n+','\n\n',text)
         text = re.sub(r' +',' ',text)
         return text

    def processHTML(self, rawhtml, title = None):
        print(f'got raw html {rawhtml}')
        url = hashlib.md5(str(rawhtml).encode()).hexdigest()
        title_search = re.search(r'<title>(.*?)</title>', string = str(rawhtml), flags = re.I | re.DOTALL)
        text = None
        entry = None
        if self.config.debug: print(f'url {url}')
        if title_search:
            title = unescape(title_search[1])
        elif not title:
            title = "Untitled Content"
        if self.config.debug: print(f'found item with title {title}')
        if trafilatura_available:
            try:
                mytree = html.fromstring(rawhtml)
                if self.config.debug: print(f'parsed html tree')
                text = trafilatura.extract(mytree, include_comments=False).replace('\n','\n\n')
                if self.config.debug: print(f'digested tree')
                title_search = trafilatura.extract_metadata(mytree).title
                if self.config.debug: print(f'extracted title')
                if title_search:
                    title = unescape(title_search)
            except:
                pass
        if not text:
            if self.config.debug: print(f'attempting pandoc extraction')
            try:
                text = self.cleanHTML(rawhtml)
            except:
                pass
        text = re.sub(r'[^A-Za-z0-9 \n_.,!"\']',' ',text)
        text = re.sub(r'^ *$','\n',text,flags = re.MULTILINE)
        text = re.sub(r'\n\n+','\n\n',text)
        text = re.sub(r' +',' ',text)
        print(f'got processed html {text}')
        time.sleep(600)
        if text:
            entry = (title, text, url)
        return entry
        
    def processText(self, text, title = None):
        if self.config.debug: print(f'found plain-text content')
        url = hashlib.md5(text.encode()).hexdigest()
        if not title:
            title = "Untitled Content"
        entry = (title, text, url)
        return entry

    def getItems(self, text, title = None):
        entries = []
        type = magic.from_buffer(text)
        if 'mail' in type.lower() or re.search(r'^return-path:', text, flags = re.I | re.MULTILINE):
            if self.config.debug: print(f'processing email')
            entries.extend(self.processEmail(text, title))
        elif '<html' in text.lower():
            if self.config.debug: print(f'processing html content')
            for i in re.findall('<html.*?</html>', string = text, flags = re.I | re.DOTALL):
                entry = self.processHTML(i, title)
                if entry:
                    entries.append(entry)
        else:
            entry = self.processText(text, title)
            if entry:
               entries.append(entry)
        return entries
