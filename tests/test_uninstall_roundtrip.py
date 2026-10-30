"""Feed synthetic manifests through the real uninstall.sh reversal logic.

The uninstaller requires root and targets absolute system paths, so — like the
existing Tor/proxychains regression — these tests extract the actual helper and
manifest-mode sections from ``uninstall.sh`` and run them against a temporary
prefix as an unprivileged user. They prove, per manifest entry type, which
reversal the script performs, and that a pre-existing file never recorded by
ChaosticTool is left untouched. End-to-end removal as root is covered by the
disposable-container checks.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "uninstall.sh").read_text()


def _slice(text, start_anchor, end_anchor):
    start = text.index(start_anchor)
    end = text.index(end_anchor, start)
    return text[start:end]


# The real helpers (confirm / _rm_file / _dir_allowed / _rm_dir / _pipx_uninstall)
# and the real manifest-mode body (parse loop + sections [1]-[6]).
HELPERS = _slice(SCRIPT, "confirm() {\n", "# -------------------------------------------"
                 "--------------------------------\n# Detection mode")
BODY = _slice(SCRIPT, "declare -a M_FILES=()",
              '# ---------------------------------------------------------------------------\n'
              'echo -e "\\n${CYAN}[7] Manifest directory')


def run_uninstall(prefix: Path, manifest_lines, *, assume_yes=1, remove_packages=0,
                  dry_run=0, stub_pipx=True, stub_gem=True):
    manifest = prefix / "manifest"
    manifest.write_text("# ChaosticTool manifest\n" + "\n".join(manifest_lines) + "\n")
    opt = prefix / "opt" / "chaostictool"
    cache = prefix / "var" / "cache" / "chaostictool"
    stubs = []
    if stub_pipx:
        stubs.append('_pipx_uninstall() { echo "PIPX_UNINSTALL $1" >>"$CALLLOG"; return 0; }')
    if stub_gem:
        stubs.append('gem() { echo "GEM $*" >>"$CALLLOG"; return 0; }')
        stubs.append('command() { if [ "$2" = gem ]; then return 0; fi; builtin command "$@"; }')
    prelude = f"""set -e
GREEN=''; RED=''; CYAN=''; YELLOW=''; DIM=''; NC=''
DRY_RUN={dry_run}
ASSUME_YES={assume_yes}
REMOVE_PACKAGES={remove_packages}
ORIG_USER=''
ORIG_HOME={prefix!s}
MANIFEST={manifest!s}
MANIFEST_DIR={prefix / 'var' / 'lib' / 'chaostictool'!s}
CALLLOG={prefix / 'calls.log'!s}
ALLOWED_DIR_PREFIXES=("{opt}" "{cache}" "{prefix / 'var' / 'lib' / 'chaostictool'}")
REMOVED=0; SKIPPED=0; FAILED=0
APT_SOURCES_REMOVED=0
"""
    harness = prelude + HELPERS + "\n" + "\n".join(stubs) + "\n" + BODY
    result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True,
                            env=dict(os.environ))
    return result


class UninstallReversalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.prefix = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def mk(self, relative, content="x", link_to=None):
        path = self.prefix / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if link_to is not None:
            path.symlink_to(link_to)
        else:
            path.write_text(content)
        return path

    def test_file_and_symlink_entries_are_removed(self):
        wrapper = self.mk("usr/local/bin/responder")
        real = self.mk("home/go/bin/subfinder")
        link = self.mk("usr/local/bin/subfinder", link_to=real)
        result = run_uninstall(self.prefix,
                               [f"file:{wrapper}", f"symlink:{link}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(wrapper.exists())
        self.assertFalse(link.exists())
        self.assertTrue(real.exists(), "symlink target (the user's binary) is kept")

    def test_pre_existing_file_not_in_manifest_is_spared(self):
        recorded = self.mk("usr/local/bin/nuclei")
        stranger = self.mk("usr/local/bin/nmap", content="distro nmap")
        result = run_uninstall(self.prefix, [f"file:{recorded}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(recorded.exists())
        self.assertTrue(stranger.exists(), "a tool ChaosticTool never recorded must survive")
        self.assertEqual(stranger.read_text(), "distro nmap")

    def test_dir_entry_inside_allow_list_is_removed(self):
        checkout = self.prefix / "opt" / "chaostictool" / "Responder"
        checkout.mkdir(parents=True)
        (checkout / "Responder.py").write_text("x")
        result = run_uninstall(self.prefix, [f"dir:{checkout}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(checkout.exists())

    def test_dir_entry_outside_allow_list_is_refused(self):
        stranger_dir = self.prefix / "home" / "precious"
        stranger_dir.mkdir(parents=True)
        (stranger_dir / "keep").write_text("keep")
        result = run_uninstall(self.prefix, [f"dir:{stranger_dir}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(stranger_dir.exists(), "a dir outside the allow-list must not be rm -rf'd")
        self.assertIn("refusing to remove unexpected directory", result.stdout)

    def test_go_and_cargo_binaries_are_removed_as_files(self):
        go_bin = self.mk("home/go/bin/ffuf")
        cargo_bin = self.mk("home/.cargo/bin/rustscan")
        result = run_uninstall(self.prefix, [f"go:{go_bin}", f"cargo:{cargo_bin}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(go_bin.exists())
        self.assertFalse(cargo_bin.exists())

    def test_pipx_and_gem_entries_invoke_the_right_uninstall(self):
        result = run_uninstall(self.prefix, ["pipx:impacket", "gem:wpscan"])
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.prefix / "calls.log").read_text()
        self.assertIn("PIPX_UNINSTALL impacket", calls)
        self.assertIn("GEM uninstall wpscan --executables --all", calls)

    def test_pkg_entries_are_listed_not_removed_by_default(self):
        result = run_uninstall(self.prefix,
                               ["pkg:apt:nmap", "pkg:apt:hydra", "pkg:pacman:sqlmap"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("sudo apt-get purge --autoremove", result.stdout)
        self.assertIn("nmap", result.stdout)
        self.assertIn("sudo pacman -Rns", result.stdout)

    def test_pkg_entries_removed_with_remove_packages_flag(self):
        # pacman is stubbed via a function so no real package manager runs.
        manifest = self.prefix / "manifest"
        manifest.write_text("pkg:pacman:wpscan\npkg:pacman:ruby\n")
        prelude = f"""set -e
GREEN=''; RED=''; CYAN=''; YELLOW=''; DIM=''; NC=''
DRY_RUN=0
ASSUME_YES=1
REMOVE_PACKAGES=1
ORIG_USER=''
ORIG_HOME={self.prefix!s}
MANIFEST={manifest!s}
MANIFEST_DIR={self.prefix / 'var' / 'lib' / 'chaostictool'!s}
CALLLOG={self.prefix / 'calls.log'!s}
ALLOWED_DIR_PREFIXES=("{self.prefix}/opt/chaostictool")
REMOVED=0; SKIPPED=0; FAILED=0
APT_SOURCES_REMOVED=0
pacman() {{ echo "PACMAN $*" >>"$CALLLOG"; return 0; }}
"""
        harness = prelude + HELPERS + "\n" + BODY
        result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.prefix / "calls.log").read_text()
        self.assertIn("PACMAN -Rns --noconfirm -- wpscan ruby", calls)

    def test_repo_entry_removes_only_the_block_and_keeps_later_sections(self):
        conf = self.prefix / "etc" / "pacman.conf"
        conf.parent.mkdir(parents=True)
        conf.write_text(
            "[options]\nHoldPkg = pacman glibc\n\n"
            "[core]\nInclude = /etc/pacman.d/mirrorlist\n\n"
            "[chaotic-aur]\nInclude = /etc/pacman.d/chaotic-mirrorlist\n"
            "[custom-user-repo]\nServer = file:///home/u/repo\n")
        result = run_uninstall(self.prefix, [f"repo:pacman:{conf}:chaotic-aur"])
        self.assertEqual(result.returncode, 0, result.stderr)
        text = conf.read_text()
        self.assertNotIn("[chaotic-aur]", text)
        self.assertNotIn("chaotic-mirrorlist", text)
        self.assertIn("[custom-user-repo]", text, "a user section after ours must survive")
        self.assertIn("[core]", text)

    def test_dry_run_changes_nothing(self):
        wrapper = self.mk("usr/local/bin/responder")
        result = run_uninstall(self.prefix, [f"file:{wrapper}"], dry_run=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(wrapper.exists(), "dry run must not remove anything")
        self.assertIn("would remove", result.stdout)


class UninstallCliTests(unittest.TestCase):
    """Argument handling that runs before the root gate (safe as non-root)."""

    def test_help_exits_zero_and_describes_options(self):
        result = subprocess.run(["bash", str(ROOT / "uninstall.sh"), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--remove-packages", result.stdout)
        self.assertIn("Pre-existing tools are never recorded", result.stdout)

    def test_unknown_option_is_rejected(self):
        result = subprocess.run(["bash", str(ROOT / "uninstall.sh"), "--not-an-option"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
