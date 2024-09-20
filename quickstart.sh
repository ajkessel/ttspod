#!/bin/bash
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
echo Just edit .venv to configure your local settings and you will be good to go.
cp -i dotenv .env
