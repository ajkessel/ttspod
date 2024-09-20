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
cp -i dotenv .env
echo Just edit .env to configure your local settings and you will be good to go.
echo -n "Do you want to edit .env now? (y/n) "
read answer
if [ "$answer" == "y" ]
then
  "${editor}" .env
fi
echo get help with ./ttspod -h
