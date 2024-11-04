"""content processor (Office documents, emails, PDF)"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from email.header import decode_header
    from html import unescape
    from lxml import html
    from os import path
    from uuid import uuid4
    import email
    import hashlib
    import magic
    import pypandoc
    import quopri
    import re
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# tts modules
from logger import Logger
from util import clean_html, clean_text

# optional modules
try:
    import pymupdf  # pymudf used to be named fitz, both are acceptable
    AVAILABLE_FITZ = True
except ImportError:
    try:
        import fitz as pymupdf
        AVAILABLE_FITZ = True
    except ImportError:
        AVAILABLE_FITZ = False
try:
    import trafilatura  # to extract readable content from webpages
    AVAILABLE_TRAFILATURA = True
except ImportError:
    AVAILABLE_TRAFILATURA = False


class Content(object):
    """content input processor"""

    def __init__(self, config, log=None):
        self.log = log if log else Logger(debug=True)
        self.config = config

    def process_email(self, text=None, title=None):
        """email input processor"""
        if isinstance(text, str):  # check if input is text or unicode
            msg = email.message_from_string(text)
        else:
            msg = email.message_from_bytes(text)
        try:
            title_search = msg.get('subject')
            if "utf-8" in title_search:
                title_search = decode_header(title_search)[0][0].decode()
            if title_search:
                title = title_search
        except Exception:  # pylint: disable=broad-except
            pass
        url = msg.get('message-id')
        if not url:
            url = self.hash_text(text)
        if title_search and not title:
            title = title_search
        elif not title:
            title = "Untitled Content"
        entry = None
        longest_plain_part = ''
        longest_html_part = ''
        entries = []
        attachments = []
        self.log.write(f'got title {title}')
        for part in msg.walk():
            self.log.write(
                f'checking MIME part with type {part.get_content_type()}')
            if part.get_content_type().lower() == 'text/plain':
                this_part = quopri.decodestring(part.get_payload(decode=True))
                if len(this_part) > len(longest_plain_part):
                    longest_plain_part = this_part
            elif part.get_content_type().lower() == 'text/html':
                this_part = part.get_payload(decode=True)
                if len(this_part) > len(longest_html_part):
                    longest_html_part = this_part
            elif self.config.attachments and part.get_content_type():
                # if anything goes wrong extracting an attachment, just move on
                # pylint: disable=broad-exception-caught
                try:
                    this_part = part.get_payload(decode=True)
                    try:
                        this_filename = part.get_filename()
                    except Exception:
                        this_filename = str(uuid4())
                    if this_part:
                        buffer_type = magic.from_buffer(this_part).lower()
                        excluded_buffers = [
                            'image', 'executable', 'zip', 'sql', 'json']
                        if any(x in buffer_type for x in excluded_buffers):
                            self.log.write(
                                f'skipping attachment of type {buffer_type}')
                        else:
                            with open(path.join(
                                self.config.attachment_path, this_filename
                            ), "wb") as f:
                                f.write(this_part)
                                self.log.write(
                                    'saving attachment: '
                                    f'{this_filename} {buffer_type}'
                                )
                                attachments.append(
                                    path.join(self.config.attachment_path, this_filename))
                except Exception:
                    pass
                # pylint: enable=broad-exception-caught
        if longest_html_part:
            longest_html_part = str(clean_html(longest_html_part))
        if "<html" in str(longest_plain_part):
            longest_plain_part = re.search(
                r'<html.*</html>', str(longest_plain_part))[0]
            longest_plain_part = str(clean_html(longest_plain_part))
        if longest_plain_part:
            longest_plain_part = longest_plain_part.decode('ascii', 'ignore')
        if len(longest_html_part) > len(longest_plain_part):
            text = longest_html_part
        elif longest_plain_part:
            text = longest_plain_part
        else:
            text = ''
        text = clean_text(text)
        if text:
            entry = (title, text, url)
            entries.append(entry)
        self.log.write(f'email entry {entry}')
        for attachment in attachments:
            # if anything goes wrong extracting an attachment, just move on
            # pylint: disable=broad-exception-caught
            try:
                self.log.write(
                    f'attempting to process attachment {attachment}')
                entry = self.process_file(attachment)
                entries.extend(entry)
                self.log.write('success')
            except Exception:
                pass
            # pylint: enable=broad-exception-caught
        return entries

    def process_html(self, raw_html, title=None):
        """clean up HTML and convert to plain text"""
        url = hashlib.md5(str(raw_html).encode()).hexdigest()
        title_search = re.search(
            r'<title>(.*?)</title>', string=str(raw_html), flags=re.I | re.DOTALL)
        text = None
        entry = None
        self.log.write(f'url {url}')
        if title_search and not title:
            title = clean_text(unescape(title_search[1]))
        elif not title:
            title = "No Title Available"
        self.log.write(f'found item with title {title}')
        # do our best with Trafilatura; if that fails, try pandoc
        # pylint: disable=broad-exception-caught
        if AVAILABLE_TRAFILATURA:
            try:
                my_tree = html.fromstring(raw_html)
                text = trafilatura.extract(
                    my_tree, include_comments=False).replace('\n', '\n\n')
                title_search = trafilatura.extract_metadata(my_tree).title
                if title_search and not title:
                    title = unescape(title_search)
            except Exception:
                pass
        if not text:
            self.log.write('attempting pandoc extraction')
            try:
                text = clean_html(raw_html)
            except Exception:
                pass
        # pylint: enable=broad-exception-caught
        text = clean_text(text)
        if text:
            entry = (title, text, url)
        return entry

    def hash_text(self, text):
        """generate a unique hash from the input text for caching"""
        my_hash = hashlib.md5(str(text).encode()).hexdigest()
        if not my_hash:
            my_hash = str(uuid4())
        return my_hash

    def process_text(self, text, title=None):
        """clean up text and convert into a TTS entry item"""
        url = self.hash_text(text)
        text = clean_text(text)
        if not title:
            title = "No Title Available"
        entry = (title, text, url)
        return entry

    def process_file(self, fname, title=None):
        """read input file and try to determine filetype"""
        with open(fname, 'rb') as f:
            c = f.read()
        buffer_type = magic.from_buffer(c).lower()
        items = []
        self.log.write(f'got file type: {buffer_type}')
        if re.search('return-path:', str(c), flags=re.MULTILINE | re.I):
            self.log.write('detected email input')
            return self.process_email(c, title)
        title = title if title else fname
        text = ""
        if "pdf" in buffer_type and AVAILABLE_FITZ:
            doc = pymupdf.Document(stream=c)
            for page in doc:
                text += page.get_text()
        elif "ascii text" in buffer_type:
            text = c.decode('ascii', 'ignore')
        else:
            try:
                text = pypandoc.convert_file(source_file=fname, to='plain', extra_args=[
                                             '--wrap=none',
                                             '--strip-comments',
                                             '--ascii',
                                             f'--lua-filter={self.config.lua_path}noimage.lua'
                                             ])
            except Exception:  # pylint: disable=broad-except
                text = ""
            if not text:
                try:
                    text = pypandoc.convert_file(source_file=fname,
                                                 format='rst',
                                                 to='plain',
                                                 extra_args=[
                                                     '--wrap=none',
                                                     '--strip-comments',
                                                     '--ascii',
                                                     '--lua-filter='
                                                     f'{self.config.lua_path}noimage.lua'
                                                 ])
                except Exception:  # pylint: disable=broad-except
                    text = ""
        self.log.write(f'process_file got cleaned text: {text}')
        if text:
            items = self.get_items(text=text, title=title)
        return items

    def get_items(self, text, title=None):
        """retrieve plain text content from specified text input"""
        entries = []
        buffer_type = (magic.from_buffer(text)).lower()
        if 'mail' in buffer_type or re.search(r'^return-path:', text, flags=re.I | re.MULTILINE):
            self.log.write('processing email')
            entries.extend(self.process_email(text, title))
        elif '<html' in text.lower():
            self.log.write('processing html content')
            for i in re.findall('<html.*?</html>', string=text, flags=re.I | re.DOTALL):
                entry = self.process_html(i, title)
                if entry:
                    entries.append(entry)
        else:
            self.log.write('processing plain text content')
            entry = self.process_text(text, title)
            if entry:
                entries.append(entry)
        return entries
