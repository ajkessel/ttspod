#!/bin/bash
printf "Directory for downloaded tortoise voices (default ./working/voices): "
read line
[ "${line}" ] || line="./working/voices"
mkdir -p "${line}"
cd "${line}"
temp=$(mktemp -d -p ./)
pushd "${temp}"
git clone --no-checkout --depth=1 https://github.com/neonbjb/tortoise-tts/ 
cd "tortoise-tts"
git checkout main -- tortoise/voices 
popd
mv "${temp}/tortoise-tts/tortoise/voices/"* .
rm -rf "${temp}"
