#!/usr/bin/env bash
# Ejecutar DENTRO de Ubuntu / WSL2 (y con internet), no en PowerShell.
set -euo pipefail
if [[ "$PWD" == /mnt/* ]]; then
  echo 'ERROR: copiá el proyecto a una carpeta de Ubuntu (por ejemplo ~/ViajeAmigosProLocal).'
  exit 2
fi
if ! command -v apt-get >/dev/null; then
  echo 'Este script está preparado para Ubuntu / Debian con apt-get.'
  exit 2
fi
sudo apt-get update
sudo apt-get install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
  python3-virtualenv autoconf automake libtool pkg-config zlib1g-dev \
  libncurses-dev cmake libffi-dev libssl-dev
python3 -m venv .env-buildozer
source .env-buildozer/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install buildozer 'cython==0.29.34'
PYTHONFORANDROID_PREREQUISITES_INSTALL_INTERACTIVE=0 buildozer -v android debug
echo 'APKs generados:'
find bin -maxdepth 1 -name '*.apk' -type f -print
