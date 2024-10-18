#!/bin/bash
cd "$(dirname "$0")"
if [ ! -e version ]
then
  echo "Could not find version file."
  exit 1
fi
current_version=$(cat version|grep '[0-9\.]*')
new_version=$(echo "${current_version}" | awk -F. -v OFS=. '{$NF += 1 ; print}')
echo "Bumping from ${current_version} to ${new_version}."
echo "${new_version}" > version
sed -i "s/^__version__.*/__version__ = '$(cat version)'/gi" ./src/ttspod/version.py
