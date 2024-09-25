#!/bin/bash
yesno() {
  echo -n "${1} (y/n) "
  read answer
  f=$(echo "${answer}" | tr "A-Z" "a-z" | grep -o '^.')
  [ "$f" == "y" ] && return 0
}
venv() {
  echo creating local python venv under current directory
  if ! yesno 'Usually this works best with all packages installed locally. If you encounter an issue installing packages from PyPI, you can try starting with system-installed packages and only add local packages as needed. Do you want to install all packages locally? (y/n)'
  then
    pipString='--system-site-packages'
  fi
  "${pyexe}" -m venv "${pipString}" .venv
  source .venv/bin/activate
  echo installing requirements
  pip3 install -r requirements.txt
  optional=$(cat 'optional-requirements.txt')
  echo 'optional requirements - you should install at least one TTS engine (Whisper, OpenAI, or Eleven)'
  echo 'also install truststore if you need to trust locally-installed certificates (e.g. due to a firewall/VPN)'
  for line in $optional
  do
    if yesno "Install optional requirement ${line}?"
    then
      pip3 install "$line"
    fi
  done
}
[ $(uname) == "Darwin" ] && MAC=1
command -v brew &> /dev/null && BREW=1
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

if [ -d "./.venv" ]
then
  if yesno 'A .venv folder already exists under `pwd`. Do you want to move it out of the way and generate fresh?'
  then
    timestamp=$(date +%s)
    mv ".venv" ".venv-${timestamp}"
    echo ".venv moved to .venv-${timestamp}"
  elif ! yesno 'Do you want to install into the existing .venv?'
  then
    skipvenv=1
  fi
fi

[ -z "${skipvenv}" ] && venv

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
