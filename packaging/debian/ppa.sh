#!/usr/bin/env bash
# Run in an Ubuntu build container. PPA_UPLOAD=0 builds without submitting.
set -euo pipefail
version=${1:?usage: packaging/debian/ppa.sh X.Y.Z [PACKAGE]}
package=${2:-chaostictool}
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 2
case $package in
    chaostictool)
        tag_prefix=v
        archive_dir=Chaostic-Tool-$version
        targets="noble:24.04 resolute:26.04 stonking:26.10"
        title=ChaosticTool
        ;;
    chaostictool-desktop)
        if [[ $version =~ ^1\. ]]; then
            tag_prefix=desktop-v
            archive_dir=Chaostic-Tool-desktop-v$version
        else
            tag_prefix=v
            archive_dir=Chaostic-Tool-$version
        fi
        targets="resolute:26.04 stonking:26.10"
        title="ChaosticTool Desktop"
        ;;
    *) exit 2 ;;
esac
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends dpkg-dev debhelper devscripts dput gnupg curl ca-certificates >/dev/null
export GNUPGHOME=$(mktemp -d)
trap 'rm -rf "$GNUPGHOME"' EXIT
gpg --batch --quiet --import <<<"${PPA_SIGNING_KEY:?set PPA_SIGNING_KEY}"
key=$(gpg --list-secret-keys --with-colons | awk -F: '$1 == "fpr" { print $10; exit }')
source_debian=$PWD/packaging/debian
out=${PPA_OUT:-$PWD/dist/ppa}
mkdir -p "$out"
if [ -n "${PPA_ORIG_TARBALL:-}" ]; then
    cp "$PPA_ORIG_TARBALL" "$out/${package}_$version.orig.tar.gz"
else
    curl -fsSL -o "$out/${package}_$version.orig.tar.gz" "https://github.com/Chaos-Tic/Chaostic-Tool/archive/refs/tags/$tag_prefix$version.tar.gz"
fi
first=1
[ -n "${PPA_ORIG_UPLOADED:-}" ] && first=0
for pair in ${PPA_TARGETS:-$targets}; do
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

  * $title $version, built from source for Ubuntu $number.

 -- Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com>  $(date -R)
EOF
    sources=-sd
    if [ "$first" = 1 ]; then sources=-sa; fi
    first=0
    (cd "$work/$package-$version" && dpkg-buildpackage -S -d "$sources" -k"$key" >/dev/null)
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
