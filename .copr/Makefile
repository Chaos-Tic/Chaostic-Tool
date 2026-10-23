srpm:
	dnf install -y rpm-build rpmdevtools
	mkdir -p $(outdir) /tmp/chaostictool-rpm/SOURCES /tmp/chaostictool-rpm/SPECS
	cp packaging/fedora/chaostictool-desktop.spec /tmp/chaostictool-rpm/SPECS/
	spectool -g -R --define '_topdir /tmp/chaostictool-rpm' /tmp/chaostictool-rpm/SPECS/chaostictool-desktop.spec
	rpmbuild -bs --define '_topdir /tmp/chaostictool-rpm' --define '_srcrpmdir $(outdir)' /tmp/chaostictool-rpm/SPECS/chaostictool-desktop.spec
