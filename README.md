# TTSPod

Real documentation to come.

But the gist of it is that this app will take various forms of content and turn it into speech and then a podcast feed.

## Inputs 

* Your Wallabag feed
* Your Pocket feed
* Your Instapaper feed (planned)
* An arbitrary URL
* An email (pipe the email into the script)
* A locally-stored HTML file (pipe into script)
* A locall-stored text file (pipe into script)

## Text-to-Speech Engines

* Whisper (free, requires substantial compute resources and probably a GPU)
* OpenAI (paid, requires an API key)
* Eleven (limited free version, requires an API key)

## Get Started
```
git clone https://github.com/ajkessel/ttspod
cd ttspod
./quickstart.sh
```

You'll need to copy [dotenv](dotenv) to `.env` and edit the settings before the app will work.
## procmail
The easiest way to feed emails to TTSPod is with a procmail receipe in `.procmailrc`. For example:
```
:0 Hc
* To: my_tts_address
| ${HOME}/ttspod/ttspod
```

## License
[MIT](LICENSE)
