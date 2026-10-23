#!/bin/sh
# Run inside a disposable Debian 13 container, with the checkout mounted at /src.
set -eu
export DEBIAN_FRONTEND=noninteractive
export PYTHONDONTWRITEBYTECODE=1
apt-get update -qq
apt-get install -y -qq cmake >/tmp/build-dependencies.log
cmake -S /src -B /tmp/build -DCMAKE_INSTALL_PREFIX=/usr
cpack --config /tmp/build/CPackConfig.cmake -G DEB -B /tmp/packages
apt-get install -y -qq /tmp/packages/*.deb >/tmp/runtime-dependencies.log
cd /tmp
export QT_QPA_PLATFORM=offscreen
export CHAOSTIC_DESKTOP_HOME=/tmp/chaostic-smoke
chaostictool-desktop --smoke-test
python3 -c 'import json,os; from pathlib import Path; result=json.loads((Path(os.environ["CHAOSTIC_DESKTOP_HOME"])/"smoke-result.json").read_text()); assert result["exit_code"] == 0 and result["status"] == "success", result'
test -z "$(find /usr/share/chaostictool-desktop -name '*.pyc' -print -quit)"
apt-get remove -y -qq chaostictool-desktop
test ! -e /usr/bin/chaostictool-desktop
test ! -e /usr/share/chaostictool-desktop
test ! -e /usr/share/applications/chaostictool-desktop.desktop
