Name:           chaostictool
Version:        1.5.0
Release:        1%{?dist}
Summary:        Terminal interface for authorized security testing
License:        MIT
URL:            https://github.com/Chaos-Tic/Chaostic-Tool
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  cmake
Requires:       python3 >= 3.11
Requires:       python3-rich >= 13.7
Requires:       python3-prompt-toolkit >= 3

%description
A terminal control surface for authorized security testing. External assessment
tools are optional and are not installed automatically by this package.

%prep
%autosetup -n Chaostic-Tool-%{version}

%build
%cmake

%install
%cmake_install

%files
%license %{_datadir}/licenses/chaostictool/LICENSE
%{_bindir}/chaostictool
%{_datadir}/chaostictool/
