srpm:
	dnf install -y rpm-build rpmdevtools
	mkdir -p $(outdir) /tmp/chaostictool-rpm/SOURCES /tmp/chaostictool-rpm/SPECS
	cp packaging/fedora/chaostictool.spec /tmp/chaostictool-rpm/SPECS/
	spectool -g -R --define '_topdir /tmp/chaostictool-rpm' /tmp/chaostictool-rpm/SPECS/chaostictool.spec
	rpmbuild -bs --define '_topdir /tmp/chaostictool-rpm' --define '_srcrpmdir $(outdir)' /tmp/chaostictool-rpm/SPECS/chaostictool.spec
