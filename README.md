# TTSPod

Real documentation to come.

But the gist of it is that this app will take various forms of content and turn it into audible speech and then a podcast feed.

## Inputs 

* Your Wallabag feed
* Your Pocket feed
* Your Instapaper feed (planned)
* An arbitrary URL
* An email (pipe the email into the script)
* A locally-stored HTML file (pipe into script)
* A locally-stored text file (pipe into script)
* Office documents/PDFs (planned)

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

You'll also need somewhere to host your RSS feed and MP3 audio files if you want to listen with a podcatcher. 

## Platforms
This should work as-is on Linux and MacOS. I'm working on Windows support. You should be able to install it in a conda/pip environment on Windows but getting rsync to work properly is tricky. Once I've solved that, I'll push a parallel quickstart script for Windows PowerShell. 

## procmail
The easiest way to feed emails to TTSPod is with a procmail receipe in `.procmailrc`. For example:
```
:0 Hc
* From: my_approved_address
* To: my_tts_address
| ${HOME}/ttspod/ttspod
```

## License
[MIT](LICENSE)

Contributions welcome.
