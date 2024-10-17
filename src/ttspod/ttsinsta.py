"""instapaper input module"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# only works if instapaper was installed
try:
    import instapaper
    AVAILABLE_INSTAPAPER = True
except ImportError:
    AVAILABLE_INSTAPAPER = False

# TTSPod modules
from logger import Logger


class TTSInsta(object):
    """instapaper input"""

    def __init__(self, config, links, log):
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.p = None
        if not (
            AVAILABLE_INSTAPAPER and
            self.config.username and
            self.config.password and
            self.config.key and
            self.config.secret
        ):
            self.log.write("instapaper support not enabled, check .env")
            return
        self.links = links
        try:
            self.p = instapaper.Instapaper(self.config.key, self.config.secret)
            self.p.login(self.config.username, self.config.password)
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(f'instapaper login failed: {err}', error=True)
        return

    def get_items(self, tag):
        """retrieve items matching tag"""
        if not self.p:
            self.log.write("instapaper support not enabled")
            return None
        folder_id = None
        try:
            folders = self.p.folders()
            folder_id = [x for x in folders if x['title']
                         == tag][0]['folder_id']
        except Exception:  # pylint: disable=broad-except
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
            entries.extend(self.links.get_items(url))
        return entries
