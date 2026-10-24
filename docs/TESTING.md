# Testing

[Back to the README](../README.md)

ChaosticTool enforces strict visual and behavioural contracts across CLI and GUI.
Tests run in continuous integration across Python 3.11, 3.12, and 3.14 on Linux,
Windows, and macOS runners.

## Running Unit and Integration Tests

From the repository root with an active Python environment:
```bash
python -m unittest discover -s tests -v
```

This executes 130 deterministic tests covering:
- Profile argument vector generation
- Target parsing, deduplication, and CIDR expansion
- PTY pseudo-terminal allocation and chunked output streaming
- Secret masking across chunk boundaries
- Private storage integrity, symlink/junction traversal prevention
- Update service caching and release throttling
- Frosted-glass UI state transitions, palette contrast, and accessibility

## Native X11 Visual Contracts

To verify UI contracts (geometry, contrast ratios, DejaVu Sans font metrics) in a headless environment:
```bash
QT_QPA_PLATFORM=xcb xvfb-run -a -s '-screen 0 1600x1000x24 -nolisten tcp' python scripts/check-native-ui.py
```

## Debian Source Package Check (Zero Pip)

To guarantee that ChaosticTool can run exclusively from packaged system dependencies on a clean distribution:
```bash
docker run --rm -v "$PWD:/src:ro" debian:trixie-slim sh /src/scripts/check-source-package.sh
```

## Smoke Testing Native Packages in Clean Containers

To test package installation, binary execution, smoke test completion, and clean uninstallation without host pollution:
```bash
# Debian / Ubuntu package test
scripts/test-install-container.sh debian:trixie-slim release/*.deb

# Fedora / Red Hat package test
scripts/test-install-container.sh fedora:41 release/*.rpm
```
