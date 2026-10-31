# Native Linux installation

ChaosticTool 2.x uses one `chaostictool` package containing the CLI and Desktop
interfaces. It replaces the earlier split Desktop package. Installing the application
does not install all external assessment tools or add third-party security repositories.

## Package files

The release workflow builds unified `.deb` and `.rpm` packages for x86-64 and ARM64.
These packages contain the tested desktop bundle plus the shared Python CLI and resolve
runtime libraries with the system package manager. No system-wide pip installation is
used. AppImages are also built for x86-64 and ARM64.

```sh
sudo apt install ./chaostictool_2.0.1_amd64.deb
# Fedora (use the exact downloaded RPM filename):
sudo dnf install ./chaostictool-2.0.1-1.x86_64.rpm
chaostictool-desktop
```

Run the GUI as a regular user. The application menu entry uses the same launcher.
Use `apt remove chaostictool` or `dnf remove chaostictool` to remove
it. User settings and results remain in the user data folder. Package removal never
removes the external security tools ChaosticTool installed at runtime: run
`sudo chaostictool-uninstall --dry-run`, then `sudo chaostictool-uninstall`, **before**
removing the package to reverse exactly what `/var/lib/chaostictool/manifest` records
(pre-existing tools are never listed); the maintainer scriptlet only prints a notice.
See the [Uninstall section of the README](../README.md#uninstall).

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

AUR recipes live under `packaging/arch`. Each tagged release publishes to the AUR,
Fedora COPR, the signed Chaos-Tic apt repository and the Ubuntu PPA, and attaches the
unified `.deb`/`.rpm`/AppImage assets to the GitHub Release. The apt repository rebuilds
immediately on release (and hourly as a fallback); COPR builds from the release's source
RPM. Updates then flow through `yay -Syu`, `dnf upgrade` or `apt upgrade` on the
configured channel.

## Native repository commands

The signed apt repository is shared with the CLI:

```sh
sudo curl -fsSLo /usr/share/keyrings/chaos-tic.gpg https://chaos-tic.github.io/apt/chaos-tic-apt.gpg
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/chaos-tic.gpg] https://chaos-tic.github.io/apt stable main' | sudo tee /etc/apt/sources.list.d/chaos-tic.list
sudo apt update
sudo apt install chaostictool
```

Arch: `yay -S chaostictool` or `paru -S chaostictool`.
Fedora COPR: `sudo dnf copr enable chaostic/chaostictool && sudo dnf install chaostictool` (or install the release RPM directly with `sudo dnf install ./downloaded-package.rpm`). Use the native manager to
remove packages and retain user data. Source installs via CMake and portable
archives remain available independently of repository synchronization.

## Windows with winget

On Windows, once the package is accepted in `microsoft/winget-pkgs`, install and update
ChaosticTool with the Windows Package Manager instead of the manual installer:

```powershell
winget install ChaosTic.ChaosticTool
winget upgrade ChaosTic.ChaosticTool
```

Each tagged release refreshes the winget manifests automatically after the first
submission. The installer (unsigned, with its SHA-256) is also attached to every GitHub Release; see
[the Windows guide](../README_WINDOWS.md) for the manual download and checksum steps.
