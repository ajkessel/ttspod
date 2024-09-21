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
    def __init__(self, config):
        self.config = config
        self.my_config = deepcopy(DEFAULT_CONFIG)
        if self.config.user_agent:
            self.my_config['DEFAULT']['USER_AGENTS']=self.config.user_agent
        return 

    def getItems(self,url):
        entries = []
        if not validators.url(url):            
            if self.config.debug: print(f"{url} does not appear to be a valid URL, skipping")
            return None
        if self.config.debug: print(f"processing {url}")
        try:
            downloaded = trafilatura.fetch_url(url,config=self.my_config)
            text = trafilatura.extract(downloaded, include_comments=False).replace('\n','\n\n')
            title = trafilatura.extract_metadata(downloaded).title
            title = title if title else url
            entry = (title, text, url)
            entries.append(entry)
            if self.config.debug: print(f'successfully processed {url} {title}')
        except:
            if self.config.debug: print(f'failed to process {url}')
        return entries
