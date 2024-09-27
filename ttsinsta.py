# optional modules
# truststore to trust local certificates
try:
    import truststore
    truststore.inject_into_ssl()
except:
    pass

try:
    import instapaper
    instapaper_available = True
except:
    instapaper_available = False

# TTSPod modules
from links import Links
from logger import Logger


class TTSInsta(object):
    def __init__(self, config, links, log):
        global instapaper_available
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.p = None
        if not (instapaper_available and self.config.username and self.config.password and self.config.key and self.config.secret):
            self.log.write("instapaper support not enabled")
            return
        self.links = links
        try:
            self.p = instapaper.Instapaper(self.config.key, self.config.secret)
            self.p.login(self.config.username, self.config.password)
        except Exception as e:
            self.log.write(f'instapaper login failed: {e}', error=True)
        return

    def getItems(self, tag):
        if not self.p:
            self.log.write("instapaper support not enabled")
            return None
        folder_id = None
        try:
            folders = self.p.folders()
            folder_id = [x for x in folders if x['title']
                         == tag][0]['folder_id']
        except:
            pass
        if tag and not tag == "ALL" and not folder_id:
            self.log.write("no folder found for {tag}")
            return None
        if tag == "ALL":
            results = self.p.bookmarks(limit=500)
        else:
            results = self.p.bookmarks(folder=folder_id, limit=500)
        urls = [x.url for x in results]
        entries = []
        for url in urls:
            entries.extend(self.links.getItems(url))
        return entries
