#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
optional=$(cat 'optional-requirements.txt')
for line in $optional
do
  echo -n "Install optional requirement ${line}? (y/n) "
  read answer
  if [ "$answer" == "y" ]
  then
    pip install "$line"
  fi
done
