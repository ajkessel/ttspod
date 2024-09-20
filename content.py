from copy import deepcopy
from html2text import html2text
from lxml import html
from html import unescape
import email
import hashlib
import magic
import re
import trafilatura
import validators

class Content(object):
    def __init__(self, config):
        self.config = config
        pass

    def processEmail(self, text, title = None):
        msg = email.message_from_string(text)
        title_search = msg.get('subject')
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
             entries = self.getItems(str(candidate),title)
             return entries
        return None

    def processHTML(self, rawhtml, title = None):
        url = hashlib.md5(rawhtml.encode()).hexdigest()
        title_search = re.search(r'<title>(.*?)</title>', string = rawhtml, flags = re.DOTALL)
        text = None
        entry = None
        if title_search:
            title = unescape(title_search[1])
        elif not title:
            title = "Untitled Content"
        if self.config.debug: print(f'found item with title {title}')
        try:
            mytree = html.fromstring(rawhtml)
            text = trafilatura.extract(mytree, include_comments=False).replace('\n','\n\n')
            title_search = trafilatura.extract_metadata(mytree).title
            if title_search:
                title = unescape(title_search)
        except:
            pass
        if not text:
            if self.config.debug: print(f'attempting html2text extraction')
            try:
                text = unescape(html2text(rawhtml))
            except:
                pass
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
        if 'mail' in type:
            if self.config.debug: print(f'processing email')
            entries.extend(self.processEmail(text, title))
        elif '<html' in text.lower():
            if self.config.debug: print(f'processing html content')
            for i in re.findall('<html.*?</html>', string = text, flags = re.DOTALL):
                entry = self.processHTML(i, title)
                if entry:
                    entries.append(entry)
        else:
            entry = self.processText(text, title)
            if entry:
               entries.append(entry)
        return entries
