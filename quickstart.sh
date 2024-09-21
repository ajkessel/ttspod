#!/bin/bash
yesno() {
  echo -n "${1} (y/n) "
  read answer
  l=${answer,,}
  f=${l:0:1}
  [ "$f" == "y" ] && return 0
}
[ $(uname) == "Darwin" ] && MAC=1
[ command -v brew &> /dev/null ] && BREW=1
[ $EDITOR ] || command -v nano 2> /dev/null && EDITOR=nano || command -v vim 2> /dev/null && EDITOR=vim || command -v vi 2> /dev/null && EDITOR=vi 

echo TTSPod Installer
echo This will set things up under your current directory `pwd`
if ! yesno 'Proceed?'
then
  echo OK, exiting.
  exit 0
fi

if ! command -v pip3 > /dev/null 2>&1
then
  echo pip3 not found, exiting.
  exit 1
fi

pyexe="python3.11"
if ! command -v "${pyexe}" &> /dev/null
then
  echo 'This is only tested with python3.11, which seems to be missing from your system.'
  if [ $MAC ] && [ $BREW ]
  then
    if yesno 'Do you want to install with homebrew?'
    then
      brew install python@3.11
    fi
  elif yeson 'Do you want to proceed anyway?'
  then
    pyexe=python3
  else
    exit 0
  fi
fi

if ! command -v "${pyexe}" &> /dev/null
then
  echo "${pyexe} not found, exiting."
  exit 1
fi

echo creating local python venv under current directory
"${pyexe}" -m venv .venv
source .venv/bin/activate
echo installing requirements
pip3 install -r requirements.txt
optional=$(cat 'optional-requirements.txt')
echo 'optional requirements - you should install at least one TTS engine (Whisper, OpenAI, or Eleven)'
for line in $optional
do
  if yesno "Install optional requirement ${line}?"
  then
    pip3 install "$line"
  fi
done
if [ $MAC ]
then
  echo 'MacOS environment detected.'
  if [ $BREW ]
  then
    if ! brew list libmagic > /dev/null 2>&1
    then
      if yesno 'ttspod requires libmagic. install with brew?'
      then
        brew install libmagic
      fi
    else
      echo libmagic already installed
    fi
  else
    echo 'tts requires libmagic, but I did not find a brew installation.'
  fi
fi

cp -i dotenv .env
echo Just edit .env to configure your local settings and you will be good to go.
if yesno "Do you want to edit .env now?"
then
  if [ -z "${EDITOR}" ]
  then
    echo no editor found
  fi
  "${EDITOR}" .env
fi
echo get help with ./ttspod -h
