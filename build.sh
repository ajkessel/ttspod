#!/bin/bash
# builds new version of ttspod
# include -u option to upload to pypi
# include -g option to push to git
if [ ! -f .venv/bin/activate ] || [ ! -e version ]
then
  echo "This does not seem to be right directory for building. Exiting."
  exit 1
fi
source .venv/bin/activate
if [ ! $(python -c 'import pkgutil; print(1 if pkgutil.find_loader("twine") else "")') ]
then 
  uv pip install twine
fi
current_version=$(cat version|grep '[0-9\.]*')
if [ -z "${current_version}" ]
then
  echo "Current version could not be read. Exiting."
  exit 1
fi
new_version=$(echo "${current_version}" | awk -F. -v OFS=. '{$NF += 1 ; print}')
echo "building new version ${new_version}"
echo "${new_version}" > version
sed -i "s/^__version__.*/__version__ = '$(cat version)'/gi" ./src/ttspod/version.py
python3 -m build --sdist
if [ "$?" != "0" ]
then
  echo Build error. Exiting.
  exit 1
fi
if ! uv pip install .[local,remote,truststore,dev] --force-reinstall
then
  echo "Local install failed. Exiting."
  exit 1
fi
if [[ "$@" == *"-u"* ]]
then
  python3 -m twine upload --verbose dist/ttspod-"${new_version}".tar.gz
else
  echo 'Not uploading. Specify -u to upload.'
fi
if [[ "$@" == *"-g"* ]]
then
  git commit -a; git push
else
  echo 'Not pushing to github. Specify -g to push.'
fi
echo "Finished building version ${new_version}."
