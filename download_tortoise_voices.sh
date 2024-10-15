#!/bin/bash
mkdir -p "working/voices"
cd "working/voices"
temp=$(mktemp -d -p ./)
pushd "${temp}"
git clone --no-checkout --depth=1 https://github.com/neonbjb/tortoise-tts/ 
cd "tortoise-tts"
git checkout main -- tortoise/voices 
popd
mv "${temp}/tortoise-tts/tortoise/voices/"* .
rm -rf "${temp}"
