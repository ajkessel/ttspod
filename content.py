from uuid import uuid4
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
from util import cleanHTML, cleanText
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
        if not url:
            url = self.hashText(text)
        if title_search:
            title = title_search
        elif not title:
            title = "Untitled Content"
        entry = None
        longest_plain_part = ''
        longest_html_part = ''
        for part in msg.walk():
            if part.get_content_type().lower() == 'text/plain':
                this_part = part.get_payload(decode=True)
                if len(this_part) > len(longest_plain_part):
                    longest_plain_part = this_part
            elif part.get_content_type().lower() == 'text/html':
                this_part = part.get_payload(decode=True)
                if len(this_part) > len(longest_html_part):
                    longest_html_part = this_part
        if longest_html_part:
            try:
                longest_html_part = str(cleanHTML(longest_html_part))
            except:
                longest_html_part = ''
        if longest_plain_part:
            longest_plain_part = longest_plain_part.decode('ascii','ignore')
        if len(longest_html_part) > len(longest_plain_part):
            text = longest_html_part
        elif longest_plain_part:
            text = longest_plain_part
        else:
            text = ''
        text = text.replace('|', '').replace('-', ' ').replace('+', ' ')
        text = text.replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2018',"'").replace(u'\u2019',"'").replace(u'\u00a0',' ')
        text = re.sub(r'[^A-Za-z\:0-9 \n\-.,!"\']',' ',text)
        text = re.sub(r'^.{1,3}$','',text,flags = re.MULTILINE)
        text = re.sub(r'^[^A-Za-z]*$','',text,flags = re.MULTILINE)
        text = re.sub(r'^ *$','\n',text,flags = re.MULTILINE)
        text = re.sub(r'\n\n+','\n\n',text)
        text = re.sub(r' +',' ',text)
        text = text.strip()
        if text:
            entry = ( title, text, url )
        if self.config.debug: print(f'email entry {entry}')
        return [ entry ]

    def processHTML(self, rawhtml, title = None):
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
                text = cleanHTML(rawhtml)
            except:
                pass
        text = cleanText(text)
        if text:
            entry = (title, text, url)
        return entry
    
    def hashText(self, text):
        try:
            hash = hashlib.md5(str(text).encode()).hexdigest()
        except:
            hash = str(uuid4())
        return hash
    
    def processText(self, text, title = None):
        url = self.hashText(text)
        text = cleanText(text)
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
            if self.config.debug: print(f'processing plain text content')
            entry = self.processText(text, title)
            if entry:
               entries.append(entry)
        return entries
