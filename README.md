# TTSPod

This is a command-line app that takes many types of content and turns them into audible speech as a podcast feed.

## Inputs 

* Your Wallabag feed
* Your Pocket feed
* Your Instapaper feed 
* An arbitrary URL
* An email (pipe the email into the script, or provide as command-line argument)
* A locally-stored HTML file
* A locally-stored text file
* Office documents/PDFs 

## Outputs

* A podcast RSS feed
* MP3 files corresponding to each input item

You'll need a webserver somewhere to host the content if you want to subscribe with your podcasting app.

## Text-to-Speech Engines

* [Coqui](https://github.com/coqui-ai/TTS) (free, requires substantial compute resources and probably a GPU)
* [Whisper](https://github.com/collabora/WhisperSpeech) (free, requires substantial compute resources and probably a GPU)
* OpenAI (paid, requires an [API key](https://platform.openai.com/api-keys))
* Eleven (limited free version or paid version, [requires an API key](https://elevenlabs.io/docs/api-reference/getting-started))

Depending on your hardware configuration, you may need to pull a more recent pytorch build to get maximum performance for your specific GPU. See [the PyTorch website](https://pytorch.org/get-started/locally/) for instructions on installing torch and torchaudio with pip for your platform. Coqui with XTTS runs reasonably fast on Linux, Mac, and Windows, although the Mac GPU (mps) support is limited compared to NVidia. Coqui with Tortoise is quite slow, especially on Mac.

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

You'll need to generate a config file (`ttspod -g`) and edit it before you can do anything. Minimal required settings include configuring your TTS speech engine preference and podcast URL.

You'll also need somewhere to host your RSS feed and MP3 audio files if you want to subscribe and listen with a podcast client. The application is set up to sync the podcast feed to a web server over ssh.

## Usage
```
usage: ttspod [-h] [-c [CONFIG]] [-g [GENERATE]] [-w [WALLABAG]] [-i [INSTA]]
              [-p [POCKET]] [-l [LOG]] [-q [QUIET]] [-d] [-r] [-f] [-t TITLE]
              [-e ENGINE] [-s] [-n] [--nogpu] [-u] [-v]
              [url ...]

Convert any content to a podcast feed.

positional arguments:
  url                   specify any number of URLs or local documents (plain
                        text, HTML, PDF, Word documents, etc) to add to your
                        podcast feed

options:
  -h, --help            show this help message and exit
  -c [CONFIG], --config [CONFIG]
                        specify path for config file (default
                        ~/.config/ttspod.ini if it exists, otherwise .env in
                        the current directory)
  -g [GENERATE], --generate [GENERATE]
                        generate a new config file(default
                        ~/.config/ttspod.ini if ~/.config exists, otherwise
                        .env in the current directory)
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
                        log all output to specified filename (default
                        ttspod.log)
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
  -n, --dry-run         do not actually create or sync audio files
  --nogpu               disable GPU support (may be necessary for Mac)
  -u, --upgrade         upgrade to latest version
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
Create a one-sentence podcast from the command-line
```
# echo this text will be turned into a podcast that I will be able to listen to later | ttspod -t 'The Title of the Podcast'
```
Turn a Word document into a podcast 
```
# ttspod my_document.docx
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
* Add audio files directly from CLI via filesystem path or URL
* Use rsync where available, only remote_sync as fallback
* Language support - right now everything assumes English
* Graphical interface
* Detect paragraph breaks for slightly longer pauses
* Unit tests!

## License
[MIT](LICENSE)

Contributions welcome.
