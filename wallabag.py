try:
    from html2text import HTML2Text
    from urllib.parse import urljoin as j
    import json
    import requests
except Exception as e:
    print(f'Failed to import required module: {e}\nDo you need to run pip install -r requirements.txt?')
    exit()

class Wallabag(object):
    def __init__(self, config):
        self.url = config.url
        self.username = config.username
        self.password = config.password
        self.client_id = config.client_id
        self.client_secret = config.client_secret
        self.debug = config.debug
        auth_url = j(self.url,'oauth/v2/token')
        auth_data = {'username': self.username,
                        'password': self.password,
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'grant_type': 'password'}
        login = requests.post(auth_url, data=auth_data)
        token = json.loads(login.content)
        if self.debug: print(self.username)
        if self.debug: print(token)
        self.access_token = token['access_token']
    def getItems(self,tag):
        entries_url = j(self.url,f'api/entries.json?tags={tag}&sort=created&order=asc&page=1&perPage=500&since=0&detail=full')
        headers = {"Authorization": f"Bearer {self.access_token}"}
        entries_request = requests.get(entries_url, headers=headers)
        entries_response = json.loads(entries_request.content)
        entries = entries_response['_embedded']['items']
        h = HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        all_entries = []
        for entry in entries:
            title = entry['title']
            text = h.handle(entry['content'])
            url = h.handle(entry['url'])
            this_entry = (title, text, url)
            all_entries.append(this_entry)
        return all_entries
