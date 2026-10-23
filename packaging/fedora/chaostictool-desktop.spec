# Frozen Python/Qt runtime, identical to the tested public desktop bundle.
%global debug_package %{nil}
%global __os_install_post %{nil}
Name:           chaostictool-desktop
Version:        1.2.0
Release:        2%{?dist}
Summary:        Desktop workspace for authorized security testing
License:        MIT
URL:            https://github.com/Chaos-Tic/Chaostic-Tool
Source0:        %{url}/releases/download/desktop-v%{version}/ChaosticTool-%{version}-linux-x64.tar.gz
Source1:        https://raw.githubusercontent.com/Chaos-Tic/Chaostic-Tool/desktop-v%{version}/LICENSE
Source2:        %{url}/releases/download/desktop-v%{version}/ChaosticTool-%{version}-linux-x64.tar.gz.sha256
ExclusiveArch:  x86_64
AutoReqProv:    no
Requires:       glibc >= 2.35
Requires:       ca-certificates, dejavu-sans-fonts
Requires:       mesa-libEGL, libglvnd-opengl, libglvnd-glx, libxkbcommon, libxkbcommon-x11
Requires:       xcb-util-cursor, xcb-util-wm, xcb-util-keysyms
Requires:       xcb-util-image, xcb-util-renderutil, libxcb, dbus-libs
Requires:       fontconfig, glib2, libstdc++, libgcc

%description
A native desktop interface for authorized security testing. This package uses
the public, tested desktop bundle with its Python/Qt runtime. User results and
settings remain separate. External assessment tools are optional.

%prep
(cd %{_sourcedir} && sha256sum -c %{SOURCE2})
%setup -q -n ChaosticTool
cp -p %{SOURCE1} LICENSE

%build
# The runtime was built and smoke-tested by the upstream release workflow.

%install
mkdir -p %{buildroot}%{_libexecdir}/chaostictool-desktop
cp -a . %{buildroot}%{_libexecdir}/chaostictool-desktop/
install -d %{buildroot}%{_bindir} %{buildroot}%{_datadir}/applications %{buildroot}%{_datadir}/icons/hicolor/scalable/apps
cat >%{buildroot}%{_bindir}/chaostictool-desktop <<'EOF'
#!/bin/sh
exec %{_libexecdir}/chaostictool-desktop/ChaosticTool "$@"
EOF
chmod 755 %{buildroot}%{_bindir}/chaostictool-desktop
cat >%{buildroot}%{_datadir}/applications/chaostictool-desktop.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=ChaosticTool Desktop
Comment=Workspace for authorized security testing
Exec=chaostictool-desktop
Icon=chaostictool-desktop
Terminal=false
Categories=Network;Utility;
StartupWMClass=ChaosticTool Desktop
EOF
install -m644 _internal/desktop/assets/icon.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/chaostictool-desktop.svg

%files
%license LICENSE
%{_bindir}/chaostictool-desktop
%{_libexecdir}/chaostictool-desktop/
%{_datadir}/applications/chaostictool-desktop.desktop
%{_datadir}/icons/hicolor/scalable/apps/chaostictool-desktop.svg
