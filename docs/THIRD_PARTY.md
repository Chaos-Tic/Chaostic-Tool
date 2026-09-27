# Third-party components

ChaosticTool code: MIT, copyright Chaos-Tic. See the root LICENSE.

- Python: Python Software Foundation license — https://docs.python.org/3/license.html
- PySide6 / Shiboken6 / Qt: licenses supplied with the corresponding distributions,
  including LGPL-3.0 and applicable component notices — https://doc.qt.io/qtforpython-6/licenses.html
  and https://code.qt.io/cgit/pyside/pyside-setup.git/.
- psutil: BSD-3-Clause — https://github.com/giampaolo/psutil/blob/master/LICENSE.
- PyInstaller (build tool and bootloader): GPL with the distribution exception
  described at https://pyinstaller.org/en/stable/license.html.
- Inno Setup (installer builder): https://jrsoftware.org/isinfo.php.

The desktop distribution keeps Qt DLLs separate and replaceable. Bundled library
license texts are copied to `_internal/licenses` during the build, along with this
notice. Source code for each dependency is available from its upstream project.
The build requirements pin the versions used. No external security tool binaries
are bundled in the installer; those retain their own licenses and installers.

Optional tools are downloaded from the URLs pinned in desktop/packages.json.
Their original archive contents and license files are retained in the user tools
directory. Release archive SHA-256 values are checked before extraction; Python
packages use their published PyPI versions. Waybackurls has no upstream checksum
file; its pinned digest was computed from the official HTTPS release artifact.
