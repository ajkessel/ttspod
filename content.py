import trafilatura
import validators
from trafilatura.settings import DEFAULT_CONFIG
from copy import deepcopy
from lxml import html
import hashlib

class Content(object):
    def __init__(self, debug = False):
        self.debug = debug
        pass
        
    def getItems(self, text, title = None):
        entries = []
        for i in re.findall('<html>.*?</html>', text):
            url = hashlib.md5(i)
            title_search = re.search(r'<title>(.*?)</title>', i)
            if title_search:
                title = title_search[1]
            elif not title:
                title = "Untitled Content"
            mytree = html.fromstring(i)
            text = trafilatura.extract(mytree, include_comments=False).replace('\n','\n\n')
            entry = (title, text, url)
            entries.append(entry)
        return entries
