# TTSPod

Real documentation to come.

But the gist of it is that this app will take various forms of content and turn it into audible speech and then a podcast feed.

## Inputs 

* Your Wallabag feed
* Your Pocket feed
* Your Instapaper feed 
* An arbitrary URL
* An email (pipe the email into the script, or provide as command-line argument)
* A locally-stored HTML file
* A locally-stored text file
* Office documents/PDFs 

## Text-to-Speech Engines

* Whisper (free, requires substantial compute resources and probably a GPU)
* OpenAI (paid, requires an API key)
* Eleven (limited free version, requires an API key)

If you are using Whisper to generate speech locally, you may need to pull a more recent pytorch build to leverage your GPU. See [the PyTorch website](https://pytorch.org/get-started/locally/) for instructions on installing torch and torchaudio with pip for your specific hardware and operating system. It seems to run reasonably fast on Windows or Linux with a GPU but is deathly slow in my MacOS experiments.

## Get Started
This should work on a Linux or MacOS box.
```
git clone https://github.com/ajkessel/ttspod
cd ttspod
./quickstart.sh
```
This application does work on Windows with conda or pip but I haven't automated the install workflow yet.

You'll need to copy [dotenv](dotenv) to `.env` and edit the settings before the app will work.

You'll also need somewhere to host your RSS feed and MP3 audio files if you want to subscribe and listen with a podcatcher. The application is set up to sync the podcast feed to a webserver over ssh.

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

## TODO
* Real installer (pip, maybe Debian, WinGet, etc)
* Command-line options for all configuration settings
* Interactive configuration
* Pocket authentication workflow
* Instapaper suport
* Process links received by email
* More TTS engines
* More customizability of podcast feed

## License
[MIT](LICENSE)

Contributions welcome.
