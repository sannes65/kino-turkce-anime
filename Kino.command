#!/bin/sh
# Kino'yu baslat (macOS: cift tikla). Durdurmak icin: ./Kino.command stop
cd "$(dirname "$0")" || exit 1
exec python3 start.py "$@"
