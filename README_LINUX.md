# ChaosticTool on Linux

The CLI and Liquid Glass Desktop interface now live together on `main`, share the
same catalog and version, and are installed by the unified `chaostictool` package.
See the [main README](README.md), [installation guide](docs/INSTALLATION.md) and
[user guide](docs/USER_GUIDE.md).

```sh
git clone https://github.com/Chaos-Tic/Chaostic-Tool.git
cd Chaostic-Tool
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-desktop.txt
python chaostic_desktop.py
```

Run `python chaostictool.py` as root only when using the interactive Linux CLI.
Run the Desktop application as the regular user; individual operations request
elevation only when needed.
