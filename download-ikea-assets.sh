#!/bin/bash
# download-ikea-assets.sh
# ========================
# Laster ned "Noto IKEA"-fontfilene (latin-varianten) direkte fra IKEA sin
# egen CDN, til assets/fonts/ ved siden av dette scriptet.
#
# Kjøres på din egen maskin (vanlig Terminal — IKKE via Claude), siden det
# trengs vanlig internett-tilgang til ikea.com.
#
# Bruk:
#   cd ~/Downloads/IKEAfood   (eller der denne fila ligger)
#   chmod +x download-ikea-assets.sh
#   ./download-ikea-assets.sh

set -e
cd "$(dirname "$0")"
mkdir -p assets/fonts

echo "Laster ned Noto IKEA (latin) …"

curl -L -o assets/fonts/noto-ikea-400.latin.woff2 \
  "https://www.ikea.com/global/assets/fonts/woff2/noto-ikea-400.latin.5a052965.woff2"

curl -L -o assets/fonts/noto-ikea-700.latin.woff2 \
  "https://www.ikea.com/global/assets/fonts/woff2/noto-ikea-700.latin.a3f10ed8.woff2"

curl -L -o assets/fonts/noto-ikea-400i.latin.woff2 \
  "https://www.ikea.com/global/assets/fonts/woff2/noto-ikea-400i.latin.9efe061f.woff2"

curl -L -o assets/fonts/noto-ikea-700i.latin.woff2 \
  "https://www.ikea.com/global/assets/fonts/woff2/noto-ikea-700i.latin.b73e03c5.woff2"

echo "Ferdig. Filene ligger i assets/fonts/:"
ls -la assets/fonts/
