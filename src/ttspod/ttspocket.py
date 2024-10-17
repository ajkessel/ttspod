"""pocket input source"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# only works if pocket was installed
try:
    import pocket
    AVAILABLE_POCKET = True
except ImportError:
    AVAILABLE_POCKET = False

from logger import Logger


class TTSPocket(object):
    """pocket input source processor"""

    def __init__(self, config, links, log=None):
        self.log = log if log else Logger(debug=True)
        self.config = config
        if (not AVAILABLE_POCKET or
            not self.config.consumer_key or
                not self.config.access_token):
            self.log.write("Pocket support not enabled")
            return
        else:
            self.links = links
            self.p = pocket.Pocket(self.config.consumer_key,
                                   self.config.access_token)

    def get_items(self, tag):
        """generate list of entries from pocket feed"""
        results = self.p.retrieve(detailType='complete', tag=tag)
        items = results['list']
        urls = [items[x]['resolved_url'] for x in results['list']]
        entries = []
        for url in urls:
            entries.extend(self.links.get_items(url))
        return entries
