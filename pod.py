import pod2gen
from ntpath import split
from os.path import getsize, join as j
from os import chmod
from sysrsync import run

class Pod(object):
    def __init__(self, config, p = None):
        self.config = config
        self.p = self.new()
        return
        
    def new(self):
        pod = pod2gen.Podcast()
        pod.name = self.config.name
        pod.website = self.config.url
        pod.feed_url = j(self.config.url,'index.rss')
        pod.description = self.config.description
        pod.author = self.config.author
        pod.image = self.config.image
        pod.language = 'en-us'
        pod.explicit = False
        pod.generate_guid()
        return pod

    def save(self):
        self.p.rss_file(self.config.rss_file, minimize=False)
        chmod(self.config.rss_file, 0o644)

    def sync(self):
        if self.config.ssh_server_path and self.config.ssh_server:
            run(source=self.config.final_path,
                destination=self.config.ssh_server_path,
                destination_ssh=self.config.ssh_server,
                sync_source_contents=True,
                options=['-a']
                )
        elif self.config.ssh_server_path:
            run(source=self.config.final_path,
                destination=self.config.ssh_server_path,
                sync_source_contents=True,
                options=['-a']
                )
        else:
            if self.debug: print("ssh_server_path not defined so not uploading results")

    def add(self, entry):
        (url, title, fullpath) = entry
        filename = split(fullpath)[1]
        size = getsize(fullpath)
        self.p.episodes.append(
            pod2gen.Episode(
            title = title,
            summary = url,
            long_summary = f'Text to speech from {url}',
            media=pod2gen.Media(f'{self.config.url}{filename}', size)
            )
        )