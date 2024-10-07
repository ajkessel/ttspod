#!/bin/bash
yesno() {
  printf "%b (y/n) " "${1}"
  read -n1 -r answer
  printf "\n"
  f=$(echo "${answer}" | tr "[:upper:]" "[:lower:]" | grep -o '^.')
  [ "$f" == "y" ] && return 0
}
check_optional() {
  VAR=',remote,'
  title 'Optional Requirements'
  yesno 'Generate speech locally on your GPU?' && VAR+=',local,'
  yesno 'Trust locally installed CA certificates?' && VAR+=',truststore,'
  yesno 'Developer modules?' && VAR+=',dev,'
  VAR="$(echo ${VAR} | sed -e 's/^,/[/' -e 's/,$/]/' -e 's/,,/,/g')"
  eval "$1='${VAR}'"
  footer
}
make_venv() {
  echo Creating local python venv under current directory.
  if ! yesno 'Usually a local venv install works best. If you encounter problems, you can try relying on system-installed packages and add local packages as needed.\nUse local packages?'; then
    pipString=' --system-site-packages'
  fi
  if ! "${pyexe}" -m venv"${pipString}" .venv; then
    echo Creating virtual environment failed.
    if [ ! -d /usr/lib/python3.11/ensurepip ]; then
      echo '/usr/lib/python3.11/ensurepip is missing.'
      if yesno 'Install system-wide python3.11-venv with apt (requires sudo privileges)?'; then
        sudo apt install python3.11 python3.11-venv python3.11-dev
        "${pyexe}" -m venv "${pipString}" .venv
      fi
    fi
  fi
  if [ ! -e .venv/bin/activate ]; then
    echo Virtual environment creation failed. Exiting.
    exit 1
  fi
  # shellcheck source=/dev/null
  source .venv/bin/activate
  check_optional add_on
  # shellcheck disable=SC2154
  echo "installing ttspod${add_on} and dependencies"  
  # shellcheck disable=SC2154
  pip3 install "ttspod${add_on}"
}
title() {
  len="${#1}"
  pad=$((30 - (len / 2)))
  padding=$(printf -- '-%.0s' $(seq 1 $pad))
  echo "${padding} ${1} ${padding}"
}
footer() {
  printf -- '--------------------------------------------------------------\n\n'
}

[ "$(uname)" == "Darwin" ] && MAC=1
command -v brew &>/dev/null && BREW=1
[ "$EDITOR" ] || command -v nano &>/dev/null && EDITOR="nano" || command -v vim &>/dev/null && EDITOR="vim" || command -v vi &>/dev/null && EDITOR="vi"

title TTSPod Installer
echo "This will set things up under your current directory $(pwd)"
if ! yesno 'Proceed?'; then
  echo OK, exiting.
  exit 0
fi

if ! command -v pip3 >/dev/null 2>&1; then
  echo pip3 not found, exiting.
  exit 1
fi
footer

title Python
pyexe="python3.11"
if ! command -v "${pyexe}" &>/dev/null; then
  echo 'This is only tested with python3.11, which seems to be missing from your system.'
  if [ "${MAC}" ] && [ "${BREW}" ]; then
    if yesno 'Do you want to install with homebrew?'; then
      brew install python@3.11
    fi
  elif yesno 'Do you want to install python3.11 with apt (requires sudo)?'; then
    if ! apt-cache search --names-only '^python3.11' | grep -q python; then
      echo 'python3.11 does not appear to be in apt sources, adding deadsnake repository'
      sudo add-apt-repository ppa:deadsnakes/ppa
      sudo apt update
    fi
    sudo apt install python3.11 python3.11-venv python3.11-dev
  elif yesno 'Do you want to proceed anyway?'; then
    pyexe=python3
  else
    exit 0
  fi
fi

if [ "${MAC}" ]; then
  if ! mdfind -name '"Python.h"' | grep -q 3.11; then
    echo Python development files seem to be missing. pip may have trouble.
  fi
elif [ ! -e '/usr/include/python3.11/Python.h' ]; then
  if yesno 'Python development files seem to be missing.\nInstall python3.11-dev with app (requires sudo)?'; then
    sudo apt install python3.11-dev
  fi
fi

if ! command -v "${pyexe}" &>/dev/null; then
  echo "${pyexe} not found, exiting."
  exit 1
fi

echo "${pyexe} located."
footer

if command -v ttspod &>/dev/null; then
  tts_path="$(dirname "$(realpath "$(command -v ttspod)")")"
else
  tts_path="./.venv/bin"
fi
if [ -f "${tts_path}/ttspod" ] && [ -f "${tts_path}/activate" ]; then
  if yesno 'ttspod is already installed.\nUpdate to latest build?'; then
    # shellcheck source=/dev/null
    source "${tts_path}/activate"
    check_optional add_on
    echo "installing ttspod${add_on} -U"
    pip install "ttspod${add_on}" -U
    exit 0
  elif ! yesno 'Continue and reinstall?'; then
    exit 1
  fi
fi

title 'venv'
if [ -d "./.venv" ]; then
  if yesno ".venv already exists under $(pwd).\nMove it out of the way and generate fresh?"; then
    timestamp=$(date +%s)
    mv ".venv" ".venv-${timestamp}"
    echo ".venv moved to .venv-${timestamp}"
  elif ! yesno 'Install into existing .venv?'; then
    skipvenv=1
  fi
fi

[ -z "${skipvenv}" ] && make_venv

footer

if [ "${MAC}" ]; then
  title 'mac install'
  echo 'MacOS environment detected.'
  if [ "${BREW}" ]; then
    if ! brew list libmagic >/dev/null 2>&1; then
      if yesno 'ttspod requires libmagic. install with brew?'; then
        brew install libmagic
      fi
    else
      echo libmagic already installed
    fi
  else
    echo 'tts requires libmagic, but could not find brew.\nbrew is available at https://brew.sh/'
  fi
  footer
fi

title 'Customize'
if [ ! -e .env ]; then
  ttspod -g
fi
echo Just edit .env to configure your local settings and you will be good to go.
echo You can also move this file to ~/.config/ttspod.ini.
if yesno "Do you want to edit .env now?"; then
  if [ -z "${EDITOR}" ]; then
    echo no editor found
  fi
  "${EDITOR}" .env
fi
footer

if command -v ttspod &>/dev/null && [ -d ~/.local/bin ]; then
  if yesno "Create symlink from ttspod into ~/.local/bin?"; then
    if [ -e ~/.local/bin/ttspod ]; then
      if yesno "Overwrite existing symlink?"; then
        rm ~/.local/bin/ttspod
      fi
    fi
    ln -s "$(which ttspod)" ~/.local/bin
    echo done.
  fi
fi
echo get help with ttspod -h
