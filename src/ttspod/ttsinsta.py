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
from util import clean_text


class TTSInsta(object):
    """instapaper input"""

    def __init__(self, config, log):
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
            self.log.write(
                "Instapaper support not enabled, check configuration file.")
            return
        try:
            self.p = instapaper.Instapaper(self.config.key, self.config.secret)
            self.p.login(self.config.username, self.config.password)
        except Exception as err:  # pylint: disable=broad-except
            if 'oauth' in str(err):
                self.log.write('Unable to log in to Instapaper with these credentials:\n'
                               f'Username: {self.config.username}\n'
                               f'Password: {self.config.password}\n'
                               f'API Key: {self.config.key}\n'
                               f'API Secret: {self.config.secret}\n'
                               'Please edit configuration and try again.\n',
                               error=True)
            else:
                self.log.write(f'Instapaper login failed: {err}', error=True)
        return

    def get_items(self, tag):
        """
        retrieve items matching tag

        :param tag: tag name to retrieve or ALL for no filtering
        """
        if not self.p:
            self.log.write("Instapaper support not enabled")
            return []
        bookmarks = self.filter_items(tag)
        if not bookmarks:
            self.log.write(f"No folder or tags found for {tag}")
            return []
        entries = []
        for bookmark in bookmarks:
            self.log.write(
                f'Instapaper content for {bookmark.title} / {bookmark.url}:\n{bookmark.text}',
                log_level=3
            )
            entries.append((bookmark.title, clean_text(
                bookmark.text), bookmark.url))
        return entries

    def filter_items(self, tag):
        """
        search for bookmarks by folder or tag

        :param tag: folder/tag name to retrieve
        """
        if tag == "ALL":
            bookmarks = self.p.bookmarks(limit=1000)
        else:
            bookmarks = self.filter_by_folder(tag)
            bookmarks.extend(self.filter_by_tag(tag))
        return bookmarks

    def filter_by_folder(self, tag):
        """
        search for bookmarks in named folder

        :param tag: folder name to retrieve
        """
        folder_id = []
        folders = self.p.folders()
        folder_id = [folder for folder in folders if folder['title']
                     == tag][0]['folder_id']
        bookmarks = self.p.bookmarks(
            folder=folder_id, limit=1000) if folder_id else []
        return bookmarks

    def filter_by_tag(self, tag):
        """
        search for bookmarks with named tag

        :param tag: tag name to retrieve
        """
        bookmarks = self.p.bookmarks(limit=1000)
        return [bookmark for bookmark in bookmarks if tag in [
            bookmark_tag.get('name') for bookmark_tag in bookmark.tags]]
