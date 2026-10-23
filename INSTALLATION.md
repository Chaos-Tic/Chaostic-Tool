# ChaosticTool Installation

ChaosticTool can be installed via official packages or directly from source.

For full instructions, architecture details, and verification:
👉 **[Read the complete Installation Guide](docs/INSTALLATION.md)**

---

## Quick Start

### Debian / Ubuntu / Kali / Parrot (Signed APT)
```sh
sudo curl -fsSLo /usr/share/keyrings/chaos-tic.gpg https://chaos-tic.github.io/apt/chaos-tic-apt.gpg
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/chaos-tic.gpg] https://chaos-tic.github.io/apt stable main' | sudo tee /etc/apt/sources.list.d/chaos-tic.list
sudo apt update
sudo apt install chaostictool
```

### Arch Linux / Manjaro (AUR)
```sh
yay -S chaostictool
```

### Fedora (COPR)
```sh
sudo dnf copr enable chaostic/chaostictool
sudo dnf install chaostictool
```

### From Git Checkout
```bash
git clone --branch linux-cli https://github.com/Chaos-Tic/Chaostic-Tool.git
cd Chaostic-Tool
sudo ./install.sh
```

See **[docs/INSTALLATION.md](docs/INSTALLATION.md)** for offline packages, CMake source packaging, installer profiles (`minimal`, `standard`, `full`), and uninstallation.
