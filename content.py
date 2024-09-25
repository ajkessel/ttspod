from os import path
from uuid import uuid4
from html import unescape
from html2text import html2text
from lxml import html
from quopri import decodestring
import email
import hashlib
import magic
import pypandoc
import pymupdf
import re
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
        if type(text) is str:
            msg = email.message_from_string(text)
        else:
            msg = email.message_from_bytes(text)
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
        entries = []
        attachments = []
        if self.config.debug: print(f'got title {title}')
        for part in msg.walk():
            if part.get_content_type().lower() == 'text/plain':
                this_part = part.get_payload(decode=True)
                if len(this_part) > len(longest_plain_part):
                    longest_plain_part = this_part
            elif part.get_content_type().lower() == 'text/html':
                this_part = part.get_payload(decode=True)
                if len(this_part) > len(longest_html_part):
                    longest_html_part = this_part
            elif self.config.attachments and part.get_content_type():
                try:
                    this_part = part.get_payload(decode=True)
                    try:
                        this_filename = part.get_filename()
                    except:
                        this_filename = str(uuid4())
                    if this_part:
                        with open(path.join(self.config.attachment_path,this_filename),"wb") as f:
                            f.write(this_part)
                            attachments.append(path.join(self.config.attachment_path,this_filename))
                except:
                    pass
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
        if self.config.debug: print(f'found text {text}')
        text = cleanText(text)
        if text:
            entry = ( title, text, url )
            entries.append(entry)
        if self.config.debug: print(f'email entry {entry}')
        for attachment in attachments:
            try:
                if self.config.debug: print(f'attempting to process attachment {attachment}')
                entry = self.processFile(attachment)
                entries.extend(entry)
                if self.config.debug: print(f'success')
            except:
                pass
        return entries

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

    def processFile(self,fname,title = None):
        try:
            with open(fname,'r') as f:
                c = f.read()
        except UnicodeDecodeError:
            with open(fname,'rb') as f:
                c = f.read()
        except:
            print(f'failed to process file {fname}')
            return None
        title = title if title else fname
        type = magic.from_buffer(c).lower()
        item = []
        if self.config.debug: print(f'got file type: {type}')
        if re.search('^return-path:', str(c), flags = re.MULTILINE | re.I):
            return self.processEmail(c, title)
        if "pdf" in type:
            doc = pymupdf.Document(stream=c)
            text = ""
            for page in doc:
                text += page.get_text()
            if text:
                items = self.getItems(text = text, title = title)
        else:
            try:
                text = pypandoc.convert_file(fname, 'plain', extra_args = ['--wrap=none', '--strip-comments', '--ascii', f'--lua-filter={self.config.lua_path}noimage.lua'])
                if self.config.debug: print(f'processFile: {text}')
                if text:
                    items = self.getItems(text = text, title = title)
            except Exception as e:
                print(f'failed to process file {fname}\nerror: {e}')
        return items

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
