#!/bin/sh
# Kino'yu baslat (Linux / WSL). Durdurmak icin: ./start.sh stop
cd "$(dirname "$0")" || exit 1
exec python3 start.py "$@"
