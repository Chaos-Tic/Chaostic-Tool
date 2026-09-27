#!/bin/sh
set -eu
destination="${XDG_DATA_HOME:-$HOME/.local/share}/ChaosticTool/application"
actual=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
expected=$(CDPATH= cd -- "$destination" && pwd)
if [ "$actual" != "$expected" ] || [ ! -f "$actual/ChaosticTool" ]; then
    printf '%s\n' 'Lancez le désinstalleur de votre installation ChaosticTool.' >&2
    exit 1
fi
rm -f -- "${XDG_DATA_HOME:-$HOME/.local/share}/applications/chaostictool.desktop"
rm -rf -- "$actual"
printf '%s\n' 'ChaosticTool désinstallé. Vos données et outils téléchargés sont conservés.'
