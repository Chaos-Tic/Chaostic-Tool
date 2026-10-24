#!/usr/bin/env bash
# Runs ./install.sh in a clean container of a distribution, as a user with sudo,
# then verifies the installed commands and uninstaller:
#   scripts/test-install-container.sh debian:stable
set -euo pipefail
cd "$(dirname "$0")/.."
image=${1:?usage: scripts/test-install-container.sh IMAGE}
engine=$(command -v docker || command -v podman) || { echo "Docker or Podman is required" >&2; exit 2; }
"$engine" run --rm -v "$PWD:/src:ro" "$image" bash -c '
set -e
export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null; then
  apt-get update -qq && apt-get install -y -qq sudo ca-certificates python3 python3-rich python3-prompt-toolkit >/dev/null
elif command -v pacman >/dev/null; then
  pacman -Sy --noconfirm --needed sudo util-linux python python-rich python-prompt_toolkit >/dev/null
elif command -v dnf >/dev/null; then
  dnf install -y -q sudo util-linux shadow-utils python3 python3-rich python3-prompt-toolkit >/dev/null
fi
useradd -m tester && echo "tester ALL=(ALL) NOPASSWD: ALL" >/etc/sudoers.d/tester
cp -r /src /home/tester/chaostictool && rm -rf /home/tester/chaostictool/{build,dist,release} && chown -R tester /home/tester/chaostictool
runuser -u tester -- bash -c "cd ~/chaostictool && sudo ./install.sh --profile minimal -y"
runuser -u tester -- bash -c "chaostictool --version && chaostictool --check-installation"
runuser -u tester -- bash -c "cd ~/chaostictool && sudo ./uninstall.sh --yes"
runuser -u tester -- bash -c "test ! -e /usr/local/bin/chaostictool && test ! -e /usr/bin/chaostictool"
echo "OK: install and uninstall verified in $image"
'
