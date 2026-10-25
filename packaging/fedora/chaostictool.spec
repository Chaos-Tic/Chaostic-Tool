# Fedora does not provide py7zr; use the release's frozen GUI runtime while the
# terminal interface uses distribution Python libraries. Both belong to one RPM.
%global debug_package %{nil}
%global __os_install_post %{nil}
Name:           chaostictool
Version:        2.0.0
Release:        1%{?dist}
Summary:        Terminal and desktop interfaces for authorized security testing
License:        MIT
URL:            https://github.com/Chaos-Tic/Chaostic-Tool
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz
Source1:        %{url}/releases/download/v%{version}/ChaosticTool-%{version}-linux-x64.tar.gz
Source2:        %{url}/releases/download/v%{version}/ChaosticTool-%{version}-linux-x64.tar.gz.sha256
ExclusiveArch:  x86_64
AutoReqProv:    no
BuildRequires:  cmake
Requires:       python3 >= 3.11
Requires:       python3-rich >= 13.7
Requires:       python3-prompt-toolkit >= 3
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
assessment tools are optional and are not installed automatically by this package.

%prep
(cd %{_sourcedir} && sha256sum -c %{SOURCE2})
%autosetup -n Chaostic-Tool-%{version}
mkdir frozen
tar -xzf %{SOURCE1} -C frozen

%build
%cmake -DCMAKE_INSTALL_LIBDIR=%{_lib} -DCHAOSTIC_BUNDLE_DIR="$PWD/frozen/ChaosticTool"

%install
%cmake_install

%files
%license %{_datadir}/licenses/chaostictool/LICENSE
%{_bindir}/chaostictool
%{_bindir}/chaostictool-desktop
%{_libdir}/chaostictool-desktop/
%{_datadir}/chaostictool/
%{_datadir}/applications/chaostictool-desktop.desktop
%{_datadir}/icons/hicolor/scalable/apps/chaostictool.svg
%{_datadir}/icons/hicolor/scalable/apps/chaostictool-desktop.svg

%changelog
* Sun Oct 25 2026 Chaos-Tic <58691435+Chaos-Tic@users.noreply.github.com> - 2.0.0-1
- Ship the terminal and desktop interfaces in one package.
