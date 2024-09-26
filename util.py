from pypandoc import convert_text
from html import unescape
import re

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
