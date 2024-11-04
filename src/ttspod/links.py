"""process webpages via URL"""
# optional system certificate trust
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

# standard modules
try:
    from copy import deepcopy
    from trafilatura.settings import DEFAULT_CONFIG
    import trafilatura
    import validators
except ImportError as e:
    print(
        f'Failed to import required module: {e}\n'
        'You may need to re-execute quickstart.sh.\n'
        'See https://github.com/ajkessel/ttspod/blob/main/README.md for details.')
    exit()

# TTSPod modules
from logger import Logger


class Links(object):
    """URL input processor"""

    def __init__(self, config, log=None):
        self.log = log if log else Logger(debug=True)
        self.config = config
        self.my_config = deepcopy(DEFAULT_CONFIG)
        if self.config.user_agent:
            self.my_config["DEFAULT"]["USER_AGENTS"] = self.config.user_agent

    def get_items(self, url, title=None):
        """retrieve content in url"""
        entries = []
        if not validators.url(url):
            self.log.write(
                f"{url} does not appear to be a valid URL, skipping")
            return None
        self.log.write(f"processing {url}")
        try:
            downloaded = trafilatura.fetch_url(url, config=self.my_config)
            text = trafilatura.extract(
                downloaded, include_comments=False, output_format="txt"
            )
            if text:
                text = text.replace("\n", "\n\n")
                if not title:
                    detect_title = trafilatura.extract_metadata(
                        downloaded).title
                    title = detect_title if detect_title else url
                entry = (title, text, url)
                entries.append(entry)
                self.log.write(f"successfully processed {url} {title}")
            else:
                self.log.write(f"failed to process {url}: no text returned")
        except Exception as err:  # pylint: disable=broad-except
            self.log.write(f"failed to process {url}: {err}")
        return entries
