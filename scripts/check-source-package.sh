#!/bin/sh
# Run inside a disposable Debian 13 container, with the checkout mounted at /src.
set -eu
export DEBIAN_FRONTEND=noninteractive
export PYTHONDONTWRITEBYTECODE=1
apt-get update -qq
apt-get install -y -qq cmake debhelper dpkg-dev >/tmp/build-dependencies.log
mkdir /tmp/source
tar -C /src -cf - CMakeLists.txt chaostic_desktop.py chaostictool.py assets core desktop modules packaging LICENSE | tar -C /tmp/source -xf -
cp -r /src/packaging/debian /tmp/source/debian
(cd /tmp/source && dpkg-buildpackage -b -us -uc >/tmp/build-source-package.log)
apt-get install -y -qq /tmp/chaostictool_*_all.deb >/tmp/runtime-dependencies.log
cd /tmp
export QT_QPA_PLATFORM=offscreen
export CHAOSTIC_DESKTOP_HOME=/tmp/chaostic-smoke
export CHAOSTIC_CLI_HOME=/tmp/chaostic-cli
chaostictool --check-installation | tee /tmp/chaostic-cli-check
grep -F 'Results directory: /tmp/chaostic-cli/targets' /tmp/chaostic-cli-check
chaostictool-desktop --smoke-test
python3 -c 'import json,os; from pathlib import Path; result=json.loads((Path(os.environ["CHAOSTIC_DESKTOP_HOME"])/"smoke-result.json").read_text()); assert result["exit_code"] == 0 and result["status"] == "success", result'
test -z "$(find /usr/share/chaostictool -name '*.pyc' -print -quit)"
apt-get remove -y -qq chaostictool
test ! -e /usr/bin/chaostictool
test ! -e /usr/bin/chaostictool-desktop
test ! -e /usr/share/chaostictool
test ! -e /usr/share/applications/chaostictool-desktop.desktop
