Documentation to come.

But the gist of it is that this app will take various forms of content and turn it into speech and then a podcast feed.

Inputs include:
* Your Wallabag feed
* Your Pocket feed
* Your Instapaper feed (planned)
* An arbitrary URL
* An email (pipe the email into the script)
* A locally-stored HTML file (pipe into script)
* A locall-stored text file (pipe into script)

TTS engines include:
* Whisper (free, requires substantial compute resources and probably a GPU)
* OpenAI (paid, requires an API key)
* Eleven (limited free version, requires an API key)

To get started:
```
git clone https://github.com/ajkessel/ttspod
cd ttspod
./quickstart.sh
```
