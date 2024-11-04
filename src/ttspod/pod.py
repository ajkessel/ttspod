"""podcast feed generator"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from datetime import datetime
    from ntpath import split
    from os import chmod
    from os.path import getsize, join as j
    import pod2gen
    import pytz
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# TTSPod modules
from logger import Logger
from remote_sync import sync as rsync


class Pod(object):
    """podcast feed generator"""

    def __init__(self, config, p=None, log=None):
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.p = p if p else self.new()

    def new(self):
        """create new feed when none exists"""
        pod = pod2gen.Podcast()
        pod.name = self.config.name
        pod.website = self.config.url
        pod.feed_url = j(self.config.url, 'index.rss')
        pod.description = self.config.description
        pod.author = self.config.author
        pod.image = self.config.image
        pod.language = 'en-us'
        pod.explicit = False
        pod.generate_guid()
        return pod

    def save(self):
        """save feed to disk"""
        self.p.rss_file(self.config.rss_file, minimize=False)
        chmod(self.config.rss_file, 0o644)

    def sync(self):
        """sync feed and mp3 files to server"""
        if self.config.ssh_server_path:
            rsync(
                source=self.config.final_path,
                destination=self.config.ssh_server_path,
                password=self.config.ssh_password,
                keyfile=self.config.ssh_keyfile,
                recursive=False,
                debug=self.config.debug,
                dry_run=False,
                size_only=True
            )
        else:
            self.log.write(
                "ssh_server_path not defined so not uploading results")

    def add(self, entry):
        """add an item to the podcast feed"""
        (url, title, fullpath) = entry
        filename = split(fullpath)[1]
        size = getsize(fullpath)
        self.p.episodes.append(
            pod2gen.Episode(
                title=title,
                summary=url,
                long_summary=f'Text to speech from {url}',
                media=pod2gen.Media(f'{self.config.url}{filename}', size),
                publication_date=datetime.now(tz=pytz.utc)
            )
        )
