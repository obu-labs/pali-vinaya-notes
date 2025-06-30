#!/bin/sh

wget -O data/brahmali.vnm "https://github.com/obu-labs/brahmali-vinaya-notes/releases/latest/download/manifest.vnm"
wget -O data/brahmali_glosses.json "https://github.com/obu-labs/brahmali-vinaya-notes/releases/latest/download/glossary.json"
curl -L -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" https://api.github.com/repos/obu-labs/suddhaso-vinaya-notes/contents/Vibhanga > data/suddhaso_vibhanga.json
