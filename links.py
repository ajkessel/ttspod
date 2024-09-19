try:
    import truststore
    truststore.inject_into_ssl()
except:
    pass

import trafilatura
import validators
from trafilatura.settings import DEFAULT_CONFIG
from copy import deepcopy

class Links(object):
    def __init__(self, debug = False):
        self.debug = debug
        self.my_config = deepcopy(DEFAULT_CONFIG)
        self.my_config['DEFAULT']['USER_AGENTS']='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
        pass
        
    def getItems(self,urls):
        global debug
        entries = []
        for url in urls:
            if validators.url(url):
                if self.debug: print(f"processing {url}")
            else:
                if self.debug: print(f"{url} does not appear to be a valid URL, skipping")
                continue
            try:
                downloaded = trafilatura.fetch_url(url,config=self.my_config)
                text = trafilatura.extract(downloaded, include_comments=False)
                title = trafilatura.extract_metadata(downloaded).title
                title = title if title else url
                entry = (title, text, url)
                entries.append(entry)
                if self.debug: print(f'successfully processed {url} {title}')
            except:
                if self.debug: print(f'failed to process {url}')
        return entries