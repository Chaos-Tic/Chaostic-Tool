#!/bin/sh
# Run only inside a disposable Debian/Ubuntu or Fedora container.
set -eu
if command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq cmake python3-rich python3-prompt-toolkit >/tmp/dependencies.log
    generator=DEB
else
    dnf install -y -q cmake rpm-build python3-rich python3-prompt-toolkit >/tmp/dependencies.log
    generator=RPM
fi
cmake -S /src -B /tmp/build -DCMAKE_INSTALL_PREFIX=/usr
cpack --config /tmp/build/CPackConfig.cmake -G "$generator" -B /packages
if [ "$generator" = DEB ]; then
    apt-get install -y -qq /packages/*.deb
else
    dnf install -y -q /packages/*.rpm
fi
cd /tmp
chaostictool --version
chaostictool --check-installation
# Import checks must not leave bytecode in package-managed directories.
test -z "$(find /usr/share/chaostictool -name '*.pyc' -print -quit)"
if [ "$generator" = DEB ]; then
    apt-get remove -y -qq chaostictool
else
    dnf remove -y -q chaostictool
fi
test ! -e /usr/bin/chaostictool
test ! -e /usr/share/chaostictool
