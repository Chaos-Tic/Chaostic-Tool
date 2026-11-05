# Fedora does not provide py7zr; use the release's frozen GUI runtime while the
# terminal interface uses distribution Python libraries. Both belong to one RPM.
%global debug_package %{nil}
%global __os_install_post %{nil}
Name:           chaostictool
Version:        2.2.2
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
Recommends:     python3-cryptography
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
        # Short names of the recorded items (last path or field component), 8 at most.
        names=$(grep -E '^(pkg|go|cargo|pipx|pip|gem|file|symlink):' "$MANIFEST" 2>/dev/null | sed 's/.*[:/]//' | grep -v '^$' | LC_ALL=C sort -u || true)
        shown=$(printf '%s\n' "$names" | head -n 8 | tr '\n' ' ')
        [ "$(printf '%s\n' "$names" | grep -c .)" -gt 8 ] && shown="$shown..."
        echo "ChaosticTool recorded $count installed item(s) in $MANIFEST:" >&2
        echo "    $shown" >&2
        echo "Removing this package does NOT remove those external tools, repository" >&2
        echo "entries or system edits; it also removes the chaostictool-uninstall command." >&2
        echo "The manifest is kept. To remove the recorded items, either reinstall" >&2
        echo "ChaosticTool and run 'sudo chaostictool-uninstall' (preview: --dry-run)," >&2
        echo "or run 'sudo ./uninstall.sh' from a source checkout." >&2
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
* Thu Nov 05 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.2.3-1
- Henon integration: export recon as the Henon exchange contract and a one-click Henon attack-map flow (run recon -> auto-export for the Henon engine).
- Hardening: symlink-safe auto-export and Henon export that reject a symlinked parent directory (CWE-59), stale-export cleanup, enforced scope exclusions, and a hardened URL sanitiser.

* Mon Nov 02 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.2.2-1
- Unified target-address parsing across the CLI and GUI: same input -> same host/url/port (bare entry defaults to https), one clear address prompt, an echo of the interpreted target, and shared strict validation.

* Mon Nov 02 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.2.1-1
- Targeting/routing: preserve the entered URL (scheme, path, query) across the subdomain scope; block a Tor-routed tool instead of launching it directly when proxychains is missing (honest route status).
- Attack-flow integrity: never-launched/blocked/not-found steps are no longer reported as success; fan-out status reflects any host failure; strict flow validation (malformed flows, out-of-range/negative preset indices); prepared steps honour the large fan-out confirmation; no crash when the target changes after preparation.
- Reporting: declared-scope statement instead of an unverifiable guarantee, no re-attribution of history; CLI runs preserved (unique output paths); bounded log excerpts.
- Documentation: version references and download links aligned to 2.2.1.

* Sun Nov 01 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.2.0-1
- Mission report export (Markdown, text, PDF, JSON); subdomain scope controls (fan-out cap with confirmation, exclusions, clearer enumerate, target-liveness warning, amass v5 enum fix); arsenal/flows UX (tool availability states incl. needs-key, honest amass emitting names, flow host counter, TUI Liquid Glass polish, i18n pill-key fix); persistent opt-in API-key file store with optional encryption (python3-cryptography recommended).

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.1.1-1
- Flows UX: deduplicated built-in attack flows and a chained execution model (preview, run-all/step modes, progress) across the CLI and desktop; editable targets in the desktop.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.1.0-1
- 2.1.0 release: shared-core alignment — security hardening, honest 46-tool catalog, single-source manifest and desktop catalog, shared run-session, PTY-backed interactive execution, and manifest-based clean install/uninstall.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.8-1
- Overhaul install/uninstall so removing ChaosticTool cleanly reverses the tools it installed while sparing pre-existing ones.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.7-1
- Route interactive execution through a PTY-backed runner with a unified process stop and reap.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.6-1
- Single-source the desktop catalog from the tool definitions with declarative GUI argument transforms.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.5-1
- Share the run-session plumbing (secret redaction, decoding, flushing) across the CLI, TUI and desktop.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.4-1
- Single-source the native packaging artifacts from the shared tool manifest.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.3-1
- Review wave 2: pytest/ruff/mypy tooling baseline, CI gates, documentation coherence, username-free diagnostic logging.

* Sat Oct 31 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.2-1
- Review wave 1: secret redaction, privilege drop, installer containment, honest 46-tool catalog, packaging and CI fixes.

* Wed Oct 28 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.1-1
- OS-secret-store API keys, nmap Shodan profile, opt-in subdomain targeting.

* Sun Oct 25 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.0-1
- Ship the terminal and desktop interfaces in one package.
