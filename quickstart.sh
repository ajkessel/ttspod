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
  VAR="$(echo ${VAR} | sed -e 's/^,/[/' -e 's/,$/]/' -e 's/,,/,/g')"
  eval "$1='${VAR}'"
  footer
}
make_venv() {
  printf "Creating local python venv under current directory.\n"
  if ! yesno 'Usually a local venv install works best, so you should answer yes to the next question.\nIf you encounter installation problems, you can try relying on system-installed packages and only install packages in your user account as needed.\nUse local packages?'; then
    pipString=' --system-site-packages'
  fi
  if ! "${pyexe}" -m venv"${pipString}" .venv; then
    printf "Creating virtual environment failed.\n"
    if [ ! -d /usr/lib/python3.11/ensurepip ]; then
      printf "/usr/lib/python3.11/ensurepip is missing.\n"
      if yesno 'Install system-wide python3.11-venv with apt (requires sudo privileges)?'; then
        sudo apt install python3.11 python3.11-venv python3.11-dev
        "${pyexe}" -m venv "${pipString}" .venv
      fi
    fi
  fi
  if [ ! -e .venv/bin/activate ]; then
    printf "Virtual environment creation failed. Exiting.\n"
    exit 1
  fi
  # shellcheck source=/dev/null
  source .venv/bin/activate
  check_optional add_on
  # shellcheck disable=SC2154
  printf "Installing ttspod%s and dependencies.\n" "${add_on}"
  # shellcheck disable=SC2154
  pip3 install "ttspod${add_on}"
  [[ "${add_on}" == *'local'* ]] && pip3 install git+https://github.com/SWivid/F5-TTS
  return 0
}
download_tortoise_voices() {
  title 'Voices'
  if ! yesno 'Install sample voices from tortoise-tts?'; then
    return 0
  fi
  printf "Directory for downloaded tortoise voices (default ./working/voices): "
  read -r line
  [ "${line}" ] || line="./working/voices"
  mkdir -p "${line}"
  if [ "$MAC" ]; then
    curl -L https://github.com/neonbjb/tortoise-tts/tarball/master | tar --strip-components=3 -C "${line}" -x -z -f - '*/tortoise/voices/'
  else
    curl -L https://github.com/neonbjb/tortoise-tts/tarball/master | tar --strip-components=3 -C "${line}" -x -z -f - --wildcards '*/tortoise/voices/'
  fi
  footer
}
download_voice_examples() {
  title 'Voice examples'
  if ! yesno 'Download sample generated voices?'; then
    return 0
  fi
  printf "Directory for downloaded generated voices (default ./working/examples): "
  read -r line
  [ "${line}" ] || line="./working/examples"
  mkdir -p "${line}"
  curl -L https://github.com/ajkessel/ttspod/tarball/voice-examples | tar --strip-components=2 -C "${line}" -x -z -f - 
  footer
}
extras() {
  download_tortoise_voices
  download_voice_examples
}
mac_install() {
  title 'Mac Install'
  echo 'MacOS environment detected.'
  if [ "${BREW}" ]; then
    if ! brew list libmagic >/dev/null 2>&1; then
      brew install libmagic
    fi
    if ! brew list enchant >/dev/null 2>&1; then
      brew install enchant
    fi
  else
    printf "ttspod requires libmagic and enchant, but could not find homebrew package manager.\nDownload from https://brew.sh/\n"
  fi
  if pip freeze | grep -q transformers; then
    echo 'Installing modified transformers for Mac MPS support.'
    pip3 install git+https://github.com/ajkessel/transformers@v4.42.4a
  fi
  footer
  return 0
}
title() {
  len="${#1}"
  pad=$((30 - (len / 2)))
  padding=$(printf -- '-%.0s' $(seq 1 $pad))
  printf "\n%s %s %s\n" "${padding}" "${1}" "${padding}"
}
footer() {
  printf -- '--------------------------------------------------------------\n\n'
}

[ "$(uname)" == "Darwin" ] && export MAC=1
command -v brew &>/dev/null && export BREW=1
[ "$EDITOR" ] || command -v nano &>/dev/null && EDITOR="nano" || command -v vim &>/dev/null && EDITOR="vim" || command -v vi &>/dev/null && EDITOR="vi"

title TTSPod Installer
printf "This will set things up under your current directory %s.\n" "$(pwd)"
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
    if ! pip3 install "ttspod${add_on}" -U
    then
      printf "Something went wrong.\n"
      exit 1
    fi
    if ! mac_install
    then
      printf "Something went wrong.\n"
    fi
    [[ "${add_on}" == *'local'* ]] && pip3 install git+https://github.com/SWivid/F5-TTS
    printf "Update complete.\n"
    extras
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

[ "${MAC}" ] && mac_install

extras

title 'Customize'
if [ -e "${HOME}/.config" ]; then
  conf="${HOME}/.config/ttspod.ini"
else
  conf=".env"
fi
if [ ! -e "${conf}" ]; then
  ttspod -g "${conf}"
else
  printf "Existing %s found, not regenerating.\nYou may need to check your settings for any updates with the current version.\n" "${conf}"
fi
printf "Just edit %s to configure your local settings and you will be good to go.\n" "${conf}"
if [ "${conf}" == ".env" ]; then
  printf "You can also move this file to ~/.config/ttspod.ini.\n"
fi
if yesno "Do you want to edit ${conf} now?"; then
  if [ -z "${EDITOR}" ]; then
    printf "No editor found.\n"
  fi
  "${EDITOR}" "${conf}"
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

printf "Get help with ttspod -h.\n\nBefore first use, run ttspod -s to sync settings and confirm valid configuration.\n"
