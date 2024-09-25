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

from links import Links

class TTSInsta(object):
    def __init__(self, config, links):
        global instapaper_available        
        self.config = config
        self.p = None
        if not (instapaper_available and self.config.username and self.config.password and self.config.key and self.config.secret):
            if self.config.debug: print("instapaper support not enabled")
            return
        self.links = links
        try:
            self.p = instapaper.Instapaper(self.config.key, self.config.secret)
            self.p.login(self.config.username, self.config.password)
        except Exception as e:
            print(f'instapaper login failed: {e}')
        return
    def getItems(self,tag):
        if not self.p:
            if self.config.debug: print("instapaper support not enabled")
            return None
        folder_id = None
        try:
            folders = self.p.folders()
            folder_id = [ x for x in folders if x['title'] == tag ][0]['folder_id']
        except:
            pass
        if tag and not tag == "ALL" and not folder_id:
            if self.config.debug: print("no folder found for {tag}")
            return None
        if tag == "ALL":
            results = self.p.bookmarks(limit = 500)
        else:
            results = self.p.bookmarks(folder = folder_id, limit = 500)
        urls = [ x.url for x in results ]
        entries = [ ]
        for url in urls:
            entries.extend(self.links.getItems(url))
        return entries
