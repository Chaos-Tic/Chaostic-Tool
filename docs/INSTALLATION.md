# Native Linux installation — 1.2 development

Two editions have separate packages: `chaostictool` (CLI) and
`chaostictool-desktop` (GUI). They can coexist. Installing either interface does
not install all external assessment tools or add third-party security repositories.

## Package files

The next desktop release builds `.deb` and `.rpm` packages for x86-64 and ARM64.
These packages contain the tested desktop bundle and resolve graphics libraries
with the system package manager. No system-wide pip installation is needed.
They are not present in the existing Desktop 1.1.5 release.

```sh
sudo apt install ./chaostictool-desktop_1.2.0_amd64.deb
# Fedora (use the exact downloaded RPM filename):
sudo dnf install ./chaostictool-desktop-1.2.0-1.x86_64.rpm
chaostictool-desktop
```

Run the GUI as a regular user. The application menu entry uses the same launcher.
Use `apt remove chaostictool-desktop` or `dnf remove chaostictool-desktop` to remove
it. User settings and results remain in the user data folder.

## Source installation with CMake

CMake stages Python files; it does not compile Python or fetch dependencies. Install
Python 3.11+, PySide6 6.8+, psutil, dnspython, py7zr and pyte with your distribution.
The development venv retains pinned dependencies for reproducible portable builds.
Debian 13 and Ubuntu 26.04 provide PySide6; older Ubuntu installations can use the
bundled package instead. The package dependencies declare these requirements.

```sh
cmake -S . -B build/native -DCMAKE_INSTALL_PREFIX=/usr/local
sudo cmake --install build/native
chaostictool-desktop
# Stage an installation without modifying the host:
DESTDIR="$PWD/staging" cmake --install build/native
```

To build a DEB or RPM from source, configure with `/usr` as prefix, then run:

```sh
cpack --config build/native/CPackConfig.cmake -G DEB
# Or RPM, with rpmbuild available:
cpack --config build/native/CPackConfig.cmake -G RPM
```

To package a tested portable bundle, configure with
`-DCHAOSTIC_BUNDLE_DIR="$PWD/dist/ChaosticTool"`. The minimum glibc dependency is
recorded from the build environment. Build on the oldest supported target; the CI
uses Ubuntu 22.04 for x86-64 and 24.04 for ARM64.

## Repository channels

AUR recipes live under `packaging/arch`. Release checksums must be filled from the
exact release source archive before upload. A placeholder deliberately blocks an
accidental build against old sources. AUR, COPR, apt repository and Ubuntu PPA
publication are separate steps: this document does not claim these channels are
already available for this development version. Once published, updates must use
`yay -Syu`, `dnf upgrade` or `apt upgrade` through the configured channel.
