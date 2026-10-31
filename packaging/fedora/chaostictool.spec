# Fedora does not provide py7zr; use the release's frozen GUI runtime while the
# terminal interface uses distribution Python libraries. Both belong to one RPM.
%global debug_package %{nil}
%global __os_install_post %{nil}
Name:           chaostictool
Version:        2.0.6
Release:        1%{?dist}
Summary:        Terminal and desktop interfaces for authorized security testing
License:        GPL-3.0-or-later
URL:            https://github.com/Chaos-Tic/Chaostic-Tool
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz
Source1:        %{url}/releases/download/v%{version}/ChaosticTool-%{version}-linux-x64.tar.gz
Source2:        %{url}/releases/download/v%{version}/ChaosticTool-%{version}-linux-x64.tar.gz.sha256
ExclusiveArch:  x86_64
AutoReqProv:    no
BuildRequires:  cmake
Requires:       python3 >= 3.11
Requires:       python3-rich >= 13.7
Requires:       python3-prompt-toolkit >= 3.0
Requires:       python3-keyring
Requires:       glibc >= 2.35
Requires:       ca-certificates, dejavu-sans-fonts
Requires:       mesa-libEGL, libglvnd-opengl, libglvnd-glx, libxkbcommon, libxkbcommon-x11
Requires:       xcb-util-cursor, xcb-util-wm, xcb-util-keysyms
Requires:       xcb-util-image, xcb-util-renderutil, libxcb, dbus-libs
Requires:       fontconfig, glib2, libstdc++, libgcc
Provides:       chaostictool-desktop = %{version}-%{release}
Obsoletes:      chaostictool-desktop < 2.0.0

%description
Terminal and graphical interfaces sharing one security testing engine. The GUI
includes the upstream Python/Qt runtime and its dependency licenses. External
assessment tools are optional and are not installed automatically by this package;
removing this package does not remove them. Run chaostictool-uninstall to review
and remove what the application installed (it reverses only the manifest under
/var/lib/chaostictool).

%prep
(cd %{_sourcedir} && sha256sum -c %{SOURCE2})
%autosetup -n Chaostic-Tool-%{version}
mkdir frozen
tar -xzf %{SOURCE1} -C frozen

%build
%cmake -DCMAKE_INSTALL_LIBDIR=%{_lib} -DCHAOSTIC_BUNDLE_DIR="$PWD/frozen/ChaosticTool"

%install
%cmake_install

%preun
# $1 == 0 means full removal (not an upgrade). Notify only; never auto-remove
# the external tools, repository entries or system edits ChaosticTool installed.
MANIFEST=/var/lib/chaostictool/manifest
if [ "$1" = 0 ] && [ -f "$MANIFEST" ]; then
    count=$(grep -cvE '^[[:space:]]*(#|$)' "$MANIFEST" 2>/dev/null || true)
    [ -n "$count" ] || count=0
    if [ "$count" -gt 0 ]; then
        echo "ChaosticTool recorded $count installed item(s) in $MANIFEST." >&2
        echo "Removing this package does NOT remove those external tools, repository" >&2
        echo "entries or system edits. To review and remove them, run:" >&2
        echo "    sudo chaostictool-uninstall --dry-run   # preview" >&2
        echo "    sudo chaostictool-uninstall             # remove what ChaosticTool installed" >&2
        echo "The manifest is kept so this can also be done later." >&2
    fi
fi

%files
%license %{_datadir}/licenses/chaostictool/LICENSE
%{_bindir}/chaostictool
%{_bindir}/chaostictool-desktop
%{_bindir}/chaostictool-uninstall
%{_libdir}/chaostictool-desktop/
%{_datadir}/chaostictool/
%{_datadir}/applications/chaostictool-desktop.desktop
%{_datadir}/icons/hicolor/scalable/apps/chaostictool.svg
%{_datadir}/icons/hicolor/scalable/apps/chaostictool-desktop.svg

%changelog
* Fri Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.6-1
- Single-source the desktop catalog from the tool definitions with declarative GUI argument transforms.

* Fri Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.5-1
- Share the run-session plumbing (secret redaction, decoding, flushing) across the CLI, TUI and desktop.

* Fri Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.4-1
- Single-source the native packaging artifacts from the shared tool manifest.

* Fri Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.3-1
- Review wave 2: pytest/ruff/mypy tooling baseline, CI gates, documentation coherence, username-free diagnostic logging.

* Fri Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.2-1
- Review wave 1: secret redaction, privilege drop, installer containment, honest 46-tool catalog, packaging and CI fixes.

* Wed Oct 28 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.1-1
- OS-secret-store API keys, nmap Shodan profile, opt-in subdomain targeting.

* Sun Oct 25 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.0-1
- Ship the terminal and desktop interfaces in one package.
