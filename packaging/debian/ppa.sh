#!/usr/bin/env bash
# Run on an Ubuntu runner or in an Ubuntu build container.
# PPA_UPLOAD=0 builds locally; without PPA_SIGNING_KEY the source stays unsigned.
set -euo pipefail
version=${1:?usage: packaging/debian/ppa.sh X.Y.Z}
[[ $# -eq 1 && $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 2
package=chaostictool
archive_dir=Chaostic-Tool-$version
# The unified package needs PySide6 >= 6.8, unavailable in Ubuntu 24.04.
targets="resolute:26.04 stonking:26.10"
if [ "${PPA_UPLOAD:-1}" = 1 ] && [ -z "${PPA_SIGNING_KEY:-}" ]; then
    echo 'PPA_SIGNING_KEY is required for publication' >&2
    exit 2
fi
privilege=()
if [ "$(id -u)" != 0 ]; then privilege=(sudo -n); fi
"${privilege[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update -qq
"${privilege[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    dpkg-dev debhelper cmake devscripts dput gnupg curl ca-certificates >/dev/null
export GNUPGHOME=$(mktemp -d)
work=
trap 'rm -rf "$GNUPGHOME"; if [ -n "$work" ]; then rm -rf "$work"; fi' EXIT
signing=(-us -uc)
if [ -n "${PPA_SIGNING_KEY:-}" ]; then
    gpg --batch --quiet --import <<<"$PPA_SIGNING_KEY"
    key=$(gpg --list-secret-keys --with-colons | awk -F: '$1 == "fpr" { print $10; exit }')
    [[ $key =~ ^[A-Fa-f0-9]{40,64}$ ]] || { echo 'No signing key found' >&2; exit 2; }
    signing=(-k"$key")
fi
source_debian=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
out=${PPA_OUT:-$PWD/dist/ppa}
mkdir -p "$out"
out=$(cd -- "$out" && pwd)
if [ -n "${PPA_ORIG_TARBALL:-}" ]; then
    cp "$PPA_ORIG_TARBALL" "$out/${package}_$version.orig.tar.gz"
else
    curl -fsSL -o "$out/${package}_$version.orig.tar.gz" "https://github.com/Chaos-Tic/Chaostic-Tool/archive/refs/tags/v$version.tar.gz"
fi
first=1
[ -n "${PPA_ORIG_UPLOADED:-}" ] && first=0
for pair in ${PPA_TARGETS:-$targets}; do
    [[ $pair =~ ^[a-z]+:[0-9]+\.[0-9]+$ ]] || { echo "Invalid PPA target: $pair" >&2; exit 2; }
    series=${pair%%:*}
    number=${pair#*:}
    full=$version-1~ppa${PPA_REVISION:-1}~ubuntu$number
    work=$(mktemp -d)
    tar -xzf "$out/${package}_$version.orig.tar.gz" -C "$work"
    mv "$work/$archive_dir" "$work/$package-$version"
    rm -rf "$work/$package-$version/debian"
    cp -r "$source_debian" "$work/$package-$version/debian"
    rm -f "$work/$package-$version/debian/ppa.sh"
    ln -s "$out/${package}_$version.orig.tar.gz" "$work/"
    cat >"$work/$package-$version/debian/changelog" <<EOF
$package ($full) $series; urgency=medium

  * ChaosticTool $version, terminal and desktop interfaces for Ubuntu $number.

 -- Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com>  $(date -R)
EOF
    sources=-sd
    if [ "$first" = 1 ]; then sources=-sa; fi
    first=0
    (cd "$work/$package-$version" && dpkg-buildpackage -S -d "$sources" "${signing[@]}" >/dev/null)
    cp "$work"/${package}_${full}* "$out/"
    rm -rf "$work"
    if [ "${PPA_UPLOAD:-1}" = 1 ]; then
        for try in 1 2 3 4; do
            force=; [ "$try" = 1 ] || force=-f
            dput $force "ppa:${PPA:-chaos-tic/chaostictool}" "$out/${package}_${full}_source.changes" && break
            [ "$try" = 4 ] && exit 1
            echo "Upload failed (attempt $try); retrying in 90 s" >&2
            sleep 90
        done
    fi
done
