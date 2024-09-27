try:
    import truststore
    truststore.inject_into_ssl()
except:
    pass

try:
    import pocket
    pocket_available = True
except:
    pocket_available = False

from links import Links
from logger import Logger

class TTSPocket(object):
    def __init__(self, config, links):
        global pocket_available        
        self.log = log if log else Logger(debug=True)
        self.config = config
        if not pocket_available or not self.config.consumer_key or not self.config.access_token:
            self.log.write("Pocket support not enabled")
            return
        self.links = links
        self.p = pocket.Pocket(self.config.consumer_key, self.config.access_token)
        return
    def getItems(self,tag):
        results = self.p.retrieve(detailType='complete',tag=tag)
        items = results['list']
        urls = [ items[x]['resolved_url'] for x in results['list'] ]
        entries = [ ]
        for url in urls:
            entries.extend(self.links.getItems(url))
        return entries
