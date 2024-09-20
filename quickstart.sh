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
echo creating local python venv under current directory
python3 -m venv .venv
source .venv/bin/activate
echo installing requirements
pip install -r requirements.txt
optional=$(cat 'optional-requirements.txt')
echo optional requirements
for line in $optional
do
  echo -n "Install optional requirement ${line}? (y/n) "
  read answer
  if [ "$answer" == "y" ]
  then
    pip install "$line"
  fi
done
if [ $(uname) == "Darwin" ]
then
  echo 'MacOS environment detected.'
  if command -v brew 2> /dev/null
  then
    if ! brew list libmagic 2> /dev/null
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
