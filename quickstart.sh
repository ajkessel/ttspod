#!/bin/bash
yesno() {
  echo -n "${1} (y/n) "
  read -n1 -r answer
  echo ""
  f=$(echo "${answer}" | tr "[:upper:]" "[:lower:]" | grep -o '^.')
  [ "$f" == "y" ] && return 0
}
check_optional() {
  VAR=''
  yesno 'install Whisper speech engine?' && VAR+=',whisper,'
  yesno 'install Coqui speech engine?' && VAR+=',coqui,'
  yesno 'install OpenAI speech engine?' && VAR+=',openai,'
  yesno 'install Eleven speech engine?' && VAR+=',eleven,'
  if [ -z "${VAR}" ]
  then
    if ! yesno 'warning: you did not select any TTS engine. Are you sure you want to continue?'
    then
      exit 1
    fi
  fi
  yesno 'install truststore?' && VAR+=',truststore,'
  VAR="$(echo ${VAR}|sed -e 's/^,/[/' -e 's/,$/]/' -e 's/,,/,/g')"
  eval "$1='"${VAR}"'"
}
make_venv() {
  echo creating local python venv under current directory
  if ! yesno 'Usually this works best with all packages installed locally. If you encounter an issue installing packages from PyPI, you can try starting with system-installed packages and only add local packages as needed. Do you use only local (rather than system) packages?'
  then
    pipString=' --system-site-packages'
  fi
  if ! "${pyexe}" -m venv"${pipString}" .venv
  then
    echo Creating virtual environment failed. 
    if [ ! -d /usr/lib/python3.11/ensurepip ]
    then
      echo '/usr/lib/python3.11/ensurepip is missing.'
      if yesno 'Do you want to try to install systemwide python3.11-venv with apt (requires sudo privileges)?'
      then
        sudo apt install python3.11-venv
        "${pyexe}" -m venv "${pipString}" .venv
      fi
    fi
  fi
  if [ ! -e .venv/bin/activate ]
  then
    echo Virtual environment creation failed. Exiting.
    exit 1
  fi
  # shellcheck source=.venv/bin/activate
  source .venv/bin/activate
  echo 'optional requirements - you should install at least one TTS engine (Whisper, Coqui "TTS", OpenAI, or Eleven)'
  echo 'also install truststore if you need to trust locally-installed certificates (e.g. due to a firewall/VPN)'
  check_optional add_on
  echo "installing ttspod${add_on} and dependencies"
  pip3 install "ttspod${add_on}"
}
title() {
  len="${#1}"
  pad=$((30-(len/2)))
  padding=$(printf -- '-%.0s' $(seq 1 $pad))
  echo "${padding} ${1} ${padding}"
}
footer() {
  printf -- '--------------------------------------------------------------\n\n'
}

[ "$(uname)" == "Darwin" ] && MAC=1
command -v brew &> /dev/null && BREW=1
[ "$EDITOR" ] || command -v nano &> /dev/null && EDITOR="nano" || command -v vim &> /dev/null && EDITOR="vim" || command -v vi &> /dev/null && EDITOR="vi" 

title TTSPod Installer
echo "This will set things up under your current directory $(pwd)"
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
footer

title Python
pyexe="python3.11"
if ! command -v "${pyexe}" &> /dev/null
then
  echo 'This is only tested with python3.11, which seems to be missing from your system.'
  if [ "${MAC}" ] && [ "${BREW}" ]
  then
    if yesno 'Do you want to install with homebrew?'
    then
      brew install python@3.11
    fi
  elif yesno 'Do you want to proceed anyway?'
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

echo "${pyexe} located."
footer

if command -v ttspod &> /dev/null
then
  tts_path=$(dirname $(realpath $(command -v ttspod)))
else
  tts_path='./.venv/bin'
fi
if [ -f "${tts_path}/ttspod" ] && [ -f "${tts_path}/activate" ]
then
  if yesno 'It appears ttspod is already installed. Do you want to update it to the latest build?'
  then
    source "${tts_path}/activate"
    check_optional add_on
    echo "installing ttspod${add_on} -U"
    pip install "ttspod${add_on}" -U
    exit 0
  fi
elif ! yesno 'Do you want to continue and reinstall?'
then
  exit 1
fi

title 'venv'
if [ -d "./.venv" ]
then
  if yesno "A .venv folder already exists under $(pwd). Do you want to move it out of the way and generate fresh?"
  then
    timestamp=$(date +%s)
    mv ".venv" ".venv-${timestamp}"
    echo ".venv moved to .venv-${timestamp}"
  elif ! yesno 'Do you want to install into the existing .venv?'
  then
    skipvenv=1
  fi
fi

[ -z "${skipvenv}" ] && make_venv

footer

if [ "${MAC}" ]
then
  title 'mac install'
  echo 'MacOS environment detected.'
  if [ "${BREW}" ]
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
  footer
fi

title 'customize'
if [ ! -e .env ]
then
  curl https://raw.githubusercontent.com/ajkessel/ttspod/refs/heads/main/examples/dotenv.env -o .env
fi
echo Just edit .env to configure your local settings and you will be good to go.
if yesno "Do you want to edit .env now?"
then
  if [ -z "${EDITOR}" ]
  then
    echo no editor found
  fi
  "${EDITOR}" .env
fi
footer

if command -v ttspod &> /dev/null && [ -d ~/.local/bin ]
then
  if yesno "Do you want to create a symlink from ttspod into ~/.local/bin?"
  then
    if [ -e ~/.local/bin/ttspod ]
    then
      if yesno "Overwrite existing symlink?"
      then
        rm ~/.local/bin/ttspod
      fi
    fi
    ln -s "$(which ttspod)" ~/.local/bin
    echo done.
  fi
fi
echo get help with ttspod -h
