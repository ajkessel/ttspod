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

class TTSPocket(object):
    def __init__(self, config):
        global pocket_available        
        if not pocket_available:
            return None
        self.config = config
        self.p = pocket.Pocket(self.config.consumer_key, self.config.access_token)
        return
        
    def getItems(self,tag):
        results = self.p.retrieve(detailType='complete',tag=tag)
        items = results['list']
        urls = [ items[x]['resolved_url'] for x in results['list'] ]
        if urls:
            links = Links(self.config.debug)
            entries = links.getItems(urls)
            return entries
        else:
            return None