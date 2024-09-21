#!/bin/bash
echo TTSPod Installer
echo This will set things up under your current directory `pwd`
echo -n "Proceed? (y/n)"
read answer
if [ "$answer" != "y" ]
then
  echo OK, exiting.
  exit 0
fi
if ! command -v pip3 > /dev/null 2>&1
then
  echo pip3 not found, exiting.
  exit 1
fi
pyexe=python3.11
if ! command -v "${pyexe}" &> /dev/null
then
  echo -n 'This is only tested with python3.11, which seems to be missing from your system. Do you want to proceed anyway? (y/n)'
  read answer
  if [ "$answer" == "y" ]]
  then
    pyexe=python3
  else
    exit 0
  fi
fi
if ! command -v "${pyexe}" &> /dev/null
then
  echo python3 not found, exiting.
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
  echo -n "Install optional requirement ${line}? (y/n) "
  read answer
  if [ "$answer" == "y" ]
  then
    pip3 install "$line"
  fi
done
if [ $(uname) == "Darwin" ]
then
  echo 'MacOS environment detected.'
  if command -v brew > /dev/null 2>&1
  then
    if ! brew list libmagic > /dev/null 2>&1
    then
      echo -n 'ttspod requires libmagic. install with brew? (y/n)'
      read answer
      if [ "$answer" == "y" ]
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
echo -n "Do you want to edit .env now? (y/n) "
read answer
if [ "$answer" == "y" ]
then
  if [ -z "${EDITOR}" ]
  then
    command -v nano 2> /dev/null && EDITOR=nano || command -v vim 2> /dev/null && EDITOR=vim || command -v vi 2> /dev/null && EDITOR=vi || echo "Can't find editor!" && exit 1
  fi
  "${EDITOR}" .env
fi
echo get help with ./ttspod -h
