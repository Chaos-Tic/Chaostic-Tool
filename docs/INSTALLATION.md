# Installation Guide

ChaosticTool provides multiple installation options depending on your environment and workflow:
- **Native package managers** (APT, AUR, COPR) for system updates and dependency resolution
- **Standalone `.deb` / `.rpm` packages** from the GitHub release
- **CMake source installation** for system staging and packaging
- **Source checkout installer (`./install.sh`)** with customizable profiles (`minimal`, `standard`, `full`)

Two editions have separate packages: `chaostictool` (CLI) and `chaostictool-desktop` (GUI). They can coexist on the same system. Installing either interface does not automatically install the entire security tool suite or modify third-party package repositories unless opted in.

---

## 1. Native Package Managers

CLI 1.5.0 includes native DEB/RPM packages and source packaging for AUR, COPR, and Ubuntu. The signed APT repository, AUR, and Fedora COPR are published and tested.

### Debian / Ubuntu / Kali / Parrot (Signed APT Repository)

Configure the signed project repository once (Debian 13+, Ubuntu 24.04+, or derivatives):

```sh
sudo curl -fsSLo /usr/share/keyrings/chaos-tic.gpg https://chaos-tic.github.io/apt/chaos-tic-apt.gpg
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/chaos-tic.gpg] https://chaos-tic.github.io/apt stable main' | sudo tee /etc/apt/sources.list.d/chaos-tic.list
sudo apt update
sudo apt install chaostictool
```

The signing key fingerprint is `B968 F27E 534B 7AD3 2C2A 026A C874 EC5C A8A6 42AE`.
To update:
```sh
sudo apt update && sudo apt upgrade chaostictool
```

### Arch / Manjaro (AUR)

Install via your preferred AUR helper:

```sh
yay -S chaostictool
# or with paru:
paru -S chaostictool
```

The [AUR recipe](https://aur.archlinux.org/packages/chaostictool) builds the tagged source archive and verifies its SHA-256 digest.

### Fedora (COPR)

Enable the official COPR repository for Fedora 43+:

```sh
sudo dnf copr enable chaostic/chaostictool
sudo dnf install chaostictool
```

*(Minimal Fedora installations may first need `sudo dnf install dnf5-plugins` for the `copr` command).*

To update:
```sh
sudo dnf upgrade chaostictool
```

---

## 2. Downloaded Packages (.deb / .rpm)

You can download pre-built packages from the [Latest Release](https://github.com/Chaos-Tic/Chaostic-Tool/releases/latest) and install them using the package manager so dependencies are automatically resolved:

```sh
# Debian / Ubuntu / Kali:
sudo apt install ./chaostictool_1.5.0_all.deb

# Fedora / RHEL:
sudo dnf install ./chaostictool-1.5.0-1.noarch.rpm
```

Verify the installation:
```sh
chaostictool --check-installation
sudo chaostictool
```

---

## 3. Installation from a Git Checkout

Clone the repository and run the setup script:

```bash
git clone --branch linux-cli https://github.com/Chaos-Tic/Chaostic-Tool.git
cd Chaostic-Tool
sudo ./install.sh
sudo chaostictool
```

### Installer Profiles

The default installer uses the `standard` profile: it installs the Python runtime, `rich`, the ChaosticTool launcher, and fast official distro packages where available. It deliberately avoids source builds and large optional stacks by default.

```bash
sudo ./install.sh --profile minimal      # Python/Rich + launcher only
sudo ./install.sh --profile standard     # default: official distro packages only
sudo ./install.sh --with-tor             # Tor/proxychains for minimal/standard profiles
sudo ./install.sh --profile full         # heavy Go/Cargo/pipx/pip/gem/source/AUR installs + Tor routing
```

### Additional Options

- `--with-kali-repo` (APT systems): add Kali package repositories for tools missing from Debian/Ubuntu.
- `--with-chaotic-aur` (Pacman systems): add Chaotic-AUR for pre-built Arch security packages.
- `--no-tools`: skip external assessment tool installation entirely.

Run `./install.sh --help` for the complete option list.

The installer detects `pacman`, `apt`, `dnf`, `zypper`, or `apk`, skips unavailable packages without aborting the run, and links registered user-installed Go, Cargo, pipx, pip, and local binaries into paths visible from root shells.

On ARM systems (e.g. Raspberry Pi OS), the `full` profile uses portable fallbacks for tools that are often absent from default distro repositories.

---

## 4. Source Staging with CMake

CMake stages Python and assets without downloading tools or Python packages. Install Python 3.11+, Rich 13.7+, and prompt_toolkit 3+ through your distribution first:

```sh
cmake -S . -B build/native -DCMAKE_INSTALL_PREFIX=/usr/local
sudo cmake --install build/native

# Stage an installation without touching the host filesystem:
DESTDIR="$PWD/staging" cmake --install build/native

# Build native DEB or RPM packages from source:
cmake -S . -B build/packages -DCMAKE_INSTALL_PREFIX=/usr
cpack --config build/packages/CPackConfig.cmake -G DEB
cpack --config build/packages/CPackConfig.cmake -G RPM
```

---

## 5. Storage and Multi-User Notes

Results live in `$XDG_DATA_HOME/chaostictool/targets` (default `~/.local/share/chaostictool/targets`).
Under `sudo`, the invoking user's home directory is used and new directories are owned by that user.
`CHAOSTIC_CLI_HOME=/absolute/path` can override the location for custom setups.

---

## 6. Uninstallation

### Package installations
Use your package manager to remove the application. User settings, target history, and external tools are preserved:
```sh
# Debian / Ubuntu:
sudo apt remove chaostictool

# Fedora:
sudo dnf remove chaostictool

# Arch:
sudo pacman -R chaostictool
```

### Script installations
For checkout-based installations, run the uninstaller:
```bash
sudo ./uninstall.sh
```
