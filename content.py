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
        if not url:
            url = hashlib.md5(str(text).encode()).hexdigest()
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
                longest_html_part = str(self.cleanHTML(longest_html_part))
            except:
                longest_html_part = ''
        if longest_plain_part:
            longest_plain_part = longest_plain_part.decode('ascii','ignore')
        print(f'longest_html_part {longest_html_part}')
        print(f'longest_plain_part {longest_plain_part}')
        if len(longest_html_part) > len(longest_plain_part):
            text = longest_html_part
        elif longest_plain_part:
            text = longest_plain_part
        else:
            text = ''
        text = text.replace('|', '').replace('-', ' ').replace('+', ' ')
        text = text.replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2018',"'").replace(u'\u2019',"'").replace(u'\u00a0',' ')
        text = re.sub(r'[^A-Za-z0-9 \n\-.,!"\']',' ',text)
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

    def cleanHTML(self, rawhtml):
         text = pypandoc.convert_text(
                    rawhtml,
                    'plain',
                    format='html',
                    extra_args=['--wrap=none', '--strip-comments']
                    )
         text = text.replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2018',"'").replace(u'\u2019',"'").replace(u'\u00a0',' ')
         text = text.encode('ascii', 'ignore').decode('ascii','ignore')
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
