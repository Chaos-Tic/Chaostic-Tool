#!/usr/bin/env bash
# Run in an Ubuntu build container. PPA_UPLOAD=0 builds without submitting.
set -euo pipefail
version=${1:?usage: packaging/debian/ppa.sh X.Y.Z}
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 2
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends dpkg-dev debhelper devscripts dput gnupg curl ca-certificates >/dev/null
export GNUPGHOME=$(mktemp -d)
trap 'rm -rf "$GNUPGHOME"' EXIT
gpg --batch --quiet --import <<<"${PPA_SIGNING_KEY:?set PPA_SIGNING_KEY}"
key=$(gpg --list-secret-keys --with-colons | awk -F: '$1 == "fpr" { print $10; exit }')
source_debian=$PWD/packaging/debian
out=$PWD/dist/ppa
mkdir -p "$out"
curl -fsSL -o "$out/chaostictool_$version.orig.tar.gz" "https://github.com/Chaos-Tic/Chaostic-Tool/archive/refs/tags/v$version.tar.gz"
first=1
for pair in noble:24.04 resolute:26.04 stonking:26.10; do
    series=${pair%%:*}
    number=${pair#*:}
    full=$version-1~ppa${PPA_REVISION:-1}~ubuntu$number
    work=$(mktemp -d)
    tar -xzf "$out/chaostictool_$version.orig.tar.gz" -C "$work"
    mv "$work/Chaostic-Tool-$version" "$work/chaostictool-$version"
    cp -r "$source_debian" "$work/chaostictool-$version/debian"
    rm -f "$work/chaostictool-$version/debian/ppa.sh"
    ln -s "$out/chaostictool_$version.orig.tar.gz" "$work/"
    cat >"$work/chaostictool-$version/debian/changelog" <<EOF
chaostictool ($full) $series; urgency=medium

  * ChaosticTool $version, built from source for Ubuntu $number.

 -- Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com>  $(date -R)
EOF
    sources=-sd
    if [ "$first" = 1 ]; then sources=-sa; fi
    first=0
    (cd "$work/chaostictool-$version" && dpkg-buildpackage -S -d "$sources" -k"$key" >/dev/null)
    cp "$work"/chaostictool_${full}* "$out/"
    rm -rf "$work"
    if [ "${PPA_UPLOAD:-1}" = 1 ]; then
        dput "ppa:${PPA:-chaos-tic/chaostictool}" "$out/chaostictool_${full}_source.changes"
    fi
done
