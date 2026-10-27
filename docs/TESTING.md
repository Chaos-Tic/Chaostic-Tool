# Testing

[Back to the README](../README.md)

The [CI workflow](../.github/workflows/ci.yml) runs the source suite on Ubuntu 24.04
with Python 3.11, 3.12 and 3.14. Its six application build jobs rerun applicable tests
with Python 3.14 on Linux, Windows and macOS before packaging. Platform-specific
skips apply: Linux PTY tests require Linux, and POSIX CLI regressions skip Windows.
See [Compatibility](COMPATIBILITY.md) for the dated baseline CI evidence and limits.

## Unit and integration tests

From the repository root, with the project's Python dependencies already available:

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

The suite covers argument vector generation, target parsing and storage, local
fixture processes, output streaming and secret masking, history cleanup protections,
update service behaviour, and Qt navigation, palettes and accessibility contracts.
It also checks English/French validation and desktop dialogs. Test counts evolve;
the runner reports the actual count and skips for each execution.

Profile tests select forms and construct commands. They do not demonstrate that every
external tool is installed or that its offensive operations work on real targets.
WSL/Kali installation, live SSH backends, network routing, Wi-Fi hardware and GPU
workloads require separate integration evidence.

## Native X11 UI checks

With Xvfb, xdotool and the Qt X11 runtime already available, run an isolated X server:

```bash
QT_QPA_PLATFORM=xcb xvfb-run -a -s '-screen 0 1600x1000x24 -nolisten tcp' python scripts/check-native-ui.py
CHAOSTIC_TEST_FONT='DejaVu Sans' QT_FONT_DPI=144 QT_QPA_PLATFORM=xcb xvfb-run -a -s '-screen 0 1600x1000x24 -nolisten tcp' python scripts/check-native-ui.py
```

These checks exercise both languages and themes at 1360×860 and 900×600, page
navigation, horizontal overflow, keyboard focus and reduced transparency. Contrast
is checked separately by the unit suite. Xvfb does not verify a KDE, GNOME or
Wayland desktop session.

## Debian source package check

This command installs build/runtime dependencies **inside a disposable Debian
container**, mounts the checkout read-only, builds source packages, installs them,
runs the Desktop diagnostic smoke test and checks removal. It does not install
packages on the host or use pip inside the container.

```bash
docker run --rm -v "$PWD:/src:ro" debian:trixie-slim sh /src/scripts/check-source-package.sh
```

## Generated binary packages

The `linux-package-install` CI job downloads the x64 build artifacts and installs,
smoke-tests and removes them in Debian Trixie, Ubuntu 24.04, Fedora 43 and Fedora 44
containers. ARM64 DEB/RPM files are built, but that job does not install them.
The workflow contains the exact container commands. It does not test packages from
a published APT/PPA/COPR repository.

The separate helper below checks the **source CLI installer** and its uninstaller
inside a disposable container. It accepts a container image, not a DEB/RPM path,
and is not called by the current CI workflow:

```bash
scripts/test-install-container.sh debian:trixie-slim
scripts/test-install-container.sh fedora:44
```

## Documentation checks

```bash
python scripts/check-docs.py
```

This verifies repository-local Markdown link and image paths. It does not verify
external URLs, anchors, compatibility statements or published package availability.
