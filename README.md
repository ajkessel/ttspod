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

* [Whisper](https://github.com/collabora/WhisperSpeech) (free, requires substantial compute resources and probably a GPU)
* [Coqui](https://github.com/coqui-ai/TTS) (free, requires substantial compute resources and probably a GPU)
* OpenAI (paid, requires an [API key](https://platform.openai.com/api-keys))
* Eleven (limited free version or paid version, [requires an API key](https://elevenlabs.io/docs/api-reference/getting-started))

If you are using Whisper to generate speech locally, you may need to pull a more recent pytorch build to leverage your GPU. See [the PyTorch website](https://pytorch.org/get-started/locally/) for instructions on installing torch and torchaudio with pip for your specific hardware and operating system. It seems to run reasonably fast on Windows or Linux with a GPU but is deathly slow in my MacOS experiments.

## Get Started
This should work "out of the box" on Linux or MacOS.
```
mkdir ttspod
cd ttspod
curl -s https://raw.githubusercontent.com/ajkessel/ttspod/refs/heads/main/quickstart.sh -o quickstart.sh
bash quickstart.sh
```
Windows install from PowerShell, not extensively tested:
```
Invoke-WebRequest 'https://raw.githubusercontent.com/ajkessel/ttspod/refs/heads/main/quickstart.ps1' -OutFile 'quickstart.ps1'
& quickstart.ps1
```

You'll need to copy [dotenv](dotenv) to `.env` and edit the settings before the app will work. Minimal required settings include configuring your TTS speech and podcast URL.

You'll also need somewhere to host your RSS feed and MP3 audio files if you want to subscribe and listen with a podcast client. The application is set up to sync the podcast feed to a web server over ssh.

## Usage
```
usage: ttspod [-h] [-c [CONFIG]] [-g [GENERATE]] [-w [WALLABAG]] [-i [INSTA]]
              [-p [POCKET]] [-l [LOG]] [-q [QUIET]] [-d] [-r] [-f] [-t TITLE]
              [-e ENGINE] [-s] [-n] [-v]
              [url ...]

Convert any content to a podcast feed.

positional arguments:
  url                   specify any number of URLs or local documents (plain
                        text, HTML, PDF, Word documents, etc) to add to your
                        podcast feed

options:
  -h, --help            show this help message and exit
  -c [CONFIG], --config [CONFIG]
                        specify path for config file (default .env in current
                        directory
  -g [GENERATE], --generate [GENERATE]
                        generate a new config file (default .env in current
                        directory)
  -w [WALLABAG], --wallabag [WALLABAG]
                        add unprocessed items with specified tag (default
                        audio) from your wallabag feed to your podcast feed
  -i [INSTA], --insta [INSTA]
                        add unprocessed items with specified tag (default
                        audio) from your instapaper feed to your podcast feed,
                        or use tag ALL for default inbox
  -p [POCKET], --pocket [POCKET]
                        add unprocessed items with specified tag (default
                        audio) from your pocket feed to your podcast feed
  -l [LOG], --log [LOG]
                        log all output to specified filename
  -q [QUIET], --quiet [QUIET]
                        no visible output (all output will go to log if
                        specified)
  -d, --debug           include debug output
  -r, --restart         wipe state file clean and start new podcast feed
  -f, --force           force addition of podcast even if cache indicates it
                        has already been added
  -t TITLE, --title TITLE
                        specify title for content provided via pipe
  -e ENGINE, --engine ENGINE
                        specify TTS engine for this session (whisper, coqui,
                        openai, eleven)
  -s, --sync            sync podcast episodes and state file
  -n, --dry-run         dry run: do not actually create or sync audio files
  -v, --version         print version number
```
### Examples
Add a URL to your podcast feed
```
# ttspod https://slashdot.org/story/24/09/24/2049204/human-reviewers-cant-keep-up-with-police-bodycam-videos-ai-now-gets-the-job
```
Update your podcast feed with all of your Wallabag items tagged "audio" that have not yet been processed
```
# ttspod -w
```
Create a podcast from the command-line
```
# echo this text will be turned into a podcast that I will be able to listen to later | ./ttspod -t 'The Title of the Podcast'
```

## Platforms
* Linux
* MacOS
* Windows

## procmail
The easiest way to feed emails to TTSPod is with a procmail recipe in `.procmailrc`. For example, this recipe will send emails from me@example.com or you@domain.com to myttsaddress@mydomain.com to this script, assuming you have a symlink to the script in `~/.local/bin`.
```
:0 Hc
* ^From:(.*\<(?)(me@example.com|you@domain.com)
* ^(To|X-Original-To):(.*\<(?)(myttsaddress@mydomain.com)
| ${HOME}/.local/bin/ttspod &> ${HOME}/log/tts.log 
```

## TODO
* Sanity checking on config settings
* Smooth migration of config settings with updates
* Command-line options for all configuration settings
* Interactive configuration
* Pocket interactive authentication workflow
* Instapaper interactive authentication workflow
* Process links received by email
* Process directly-emailed mp3s and links to mp3s
* Allow configuration of TTS models/voices/speeds/etc
* More customizations for podcast feed
* Add audio files from CLI via filesystem path or URL
* Use rsync where available, only remote_sync as fallback
* Language support - right now everything assumes English
* Graphical interface
* Unit tests!

## License
[MIT](LICENSE)

Contributions welcome.
