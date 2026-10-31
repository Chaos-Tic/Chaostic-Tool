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
import sys
import tempfile
import unittest
from pathlib import Path

if not sys.platform.startswith("linux"):
    # uninstall.sh is the Linux uninstaller: bash 4 associative arrays,
    # apt/dnf/pacman, root detection via geteuid. macOS and Windows ship their
    # own uninstall path and never run it. Raising here skips the whole module
    # at discovery time instead of failing at import on hosts without
    # os.geteuid (Windows) or running it under bash 3.2 (macOS).
    raise unittest.SkipTest("uninstall.sh is the Linux uninstaller")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "uninstall.sh").read_text()


def _slice(text, start_anchor, end_anchor):
    start = text.index(start_anchor)
    end = text.index(end_anchor, start)
    return text[start:end]


# The real helpers (confirm / _rm_file / _dir_allowed / _rm_dir / _pipx_uninstall /
# _pip_uninstall), the real detection-mode functions, the real no-manifest gate
# and the real manifest-mode body (parse loop + sections [1]-[7]).
DASHES = "# ---------------------------------------------------------------------------\n"
HELPERS = _slice(SCRIPT, "confirm() {\n", DASHES + "# Detection mode")
DETECT = _slice(SCRIPT, "detect_and_remove() {\n", DASHES + "# No manifest")
GATE = _slice(SCRIPT, 'if [ ! -f "$MANIFEST" ]; then\n', DASHES + "# Parse manifest into typed arrays")
BODY = _slice(SCRIPT, "declare -a M_FILES=()", DASHES + 'echo -e "\\n${CYAN}=== Summary ===')


def run_uninstall(prefix: Path, manifest_lines, *, assume_yes=1, remove_packages=0,
                  dry_run=0, stub_pipx=True, stub_gem=True, stub_pip=True, extra_prelude="",
                  body=None):
    manifest = prefix / "manifest"
    manifest.write_text("# ChaosticTool manifest\n" + "\n".join(manifest_lines) + "\n")
    opt = prefix / "opt" / "chaostictool"
    cache = prefix / "var" / "cache" / "chaostictool"
    stubs = []
    if stub_pipx:
        stubs.append('_pipx_uninstall() { echo "PIPX_UNINSTALL $1" >>"$CALLLOG"; return 0; }')
    if stub_pip:
        stubs.append('_pip_uninstall() { echo "PIP_UNINSTALL $1" >>"$CALLLOG"; return 0; }')
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
""" + extra_prelude
    harness = prelude + HELPERS + "\n" + "\n".join(stubs) + "\n" + (body or BODY)
    result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True,
                            env=dict(os.environ), stdin=subprocess.DEVNULL)
    return result


def run_detection(prefix: Path, *, assume_yes, force_detect, dry_run=0):
    """Run the real no-manifest gate + detection mode with logging removal stubs.

    _rm_file/_rm_dir only log, so the hard-coded system paths detection scans
    are never touched; /etc/ in the detection body is redirected into the
    prefix so a Tor backup on the host cannot be picked up. The log proves
    whether a removal was attempted at all.
    """
    prelude = f"""set -e
GREEN=''; RED=''; CYAN=''; YELLOW=''; DIM=''; NC=''
DRY_RUN={dry_run}
ASSUME_YES={assume_yes}
FORCE_DETECT={force_detect}
ORIG_USER=''
ORIG_HOME={prefix!s}
SCRIPT_DIR={prefix!s}
MANIFEST={prefix / 'no-such-manifest'!s}
MANIFEST_DIR={prefix / 'var' / 'lib' / 'chaostictool'!s}
CALLLOG={prefix / 'calls.log'!s}
ALLOWED_DIR_PREFIXES=("/opt/chaostictool" "/var/cache/chaostictool" "{prefix}")
REMOVED=0; SKIPPED=0; FAILED=0
"""
    stubs = """
_rm_file() { echo "RM_FILE $1" >>"$CALLLOG"; }
_rm_dir() { echo "RM_DIR $1" >>"$CALLLOG"; }
_pipx_uninstall() { echo "PIPX_UNINSTALL $1" >>"$CALLLOG"; }
pipx() { return 1; }
gem() { return 1; }
"""
    detect = DETECT.replace("/etc/", f"{prefix}/etc/")
    harness = prelude + HELPERS + detect + stubs + GATE
    return subprocess.run(["bash", "-c", harness], capture_output=True, text=True,
                          env=dict(os.environ), stdin=subprocess.DEVNULL)


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

    def test_pip_entry_invokes_pip_uninstall_and_dry_run_only_announces_it(self):
        result = run_uninstall(self.prefix, ["pip:xsstrike", "pip:shodan"])
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.prefix / "calls.log").read_text()
        self.assertIn("PIP_UNINSTALL xsstrike", calls)
        self.assertIn("PIP_UNINSTALL shodan", calls)
        self.assertIn("pip uninstalled", result.stdout)
        (self.prefix / "calls.log").unlink()
        result = run_uninstall(self.prefix, ["pip:xsstrike"], dry_run=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.prefix / "calls.log").exists(), "dry run must not call pip")
        self.assertIn("would pip uninstall: xsstrike", result.stdout)

    def test_dry_run_is_a_true_no_op_for_every_entry_type_and_the_manifest_dir(self):
        # One manifest exercising every entry type, plus the manifest directory
        # itself and a Tor backup. Under --dry-run nothing on disk may change and
        # no package manager may be invoked, yet the whole plan must be printed
        # without prompting (stdin is not a terminal here).
        wrapper = self.mk("usr/local/bin/responder")
        real = self.mk("home/go/bin/subfinder")
        link = self.mk("usr/local/bin/subfinder", link_to=real)
        cargo_bin = self.mk("home/.cargo/bin/rustscan")
        checkout = self.prefix / "opt" / "chaostictool" / "Responder"
        checkout.mkdir(parents=True)
        (checkout / "Responder.py").write_text("x")
        conf_text = "[core]\nInclude = /x\n\n[chaotic-aur]\nInclude = /y\n"
        conf = self.mk("etc/pacman.conf", content=conf_text)
        torrc = self.mk("etc/tor/torrc", content="modified")
        backup = self.mk("etc/tor/torrc.chaostictool.bak", content="original")
        manifest_dir = self.prefix / "var" / "lib" / "chaostictool"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest").write_text("copy")
        lines = [f"dir:{manifest_dir}", f"file:{wrapper}", f"symlink:{link}", f"dir:{checkout}",
                 f"go:{real}", f"cargo:{cargo_bin}", "pipx:impacket", "pip:xsstrike", "gem:wpscan",
                 f"repo:pacman:{conf}:chaotic-aur", "torrc:/etc/tor/torrc", "pkg:pacman:wpscan"]
        body = BODY.replace("/etc/tor/", f"{self.prefix}/etc/tor/")
        result = run_uninstall(self.prefix, lines, dry_run=1, remove_packages=1, body=body,
                               extra_prelude='pacman() { echo "PACMAN $*" >>"$CALLLOG"; }\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in (wrapper, real, link, cargo_bin, checkout / "Responder.py", conf, torrc, backup,
                     manifest_dir / "manifest"):
            self.assertTrue(path.exists() or path.is_symlink(), f"dry run deleted {path}")
        self.assertEqual(conf.read_text(), conf_text, "dry run edited pacman.conf")
        self.assertEqual(torrc.read_text(), "modified", "dry run restored the Tor backup")
        self.assertFalse((self.prefix / "calls.log").exists(),
                         "dry run invoked pipx/pip/gem/pacman")
        out = result.stdout
        for expected in ("would remove: " + str(wrapper), "would remove: " + str(link),
                         f"would remove dir: {checkout}", "would remove: " + str(real),
                         "would remove: " + str(cargo_bin), "would pipx uninstall: impacket",
                         "would pip uninstall: xsstrike", "would gem uninstall: wpscan",
                         f"would remove repo section: [chaotic-aur] from {conf}",
                         f"would restore: {torrc}", "pacman -Rns --noconfirm -- wpscan",
                         f"would remove dir: {manifest_dir}"):
            self.assertIn(expected, out)
        self.assertNotIn("[y/N]", out, "a dry run must print the plan without prompting")
        self.assertNotIn("non-interactive", out)

    def test_manifest_dir_is_removed_after_a_clean_run(self):
        manifest_dir = self.prefix / "var" / "lib" / "chaostictool"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "manifest").write_text("copy")
        wrapper = self.mk("usr/local/bin/responder")
        result = run_uninstall(self.prefix, [f"dir:{manifest_dir}", f"file:{wrapper}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(wrapper.exists())
        self.assertFalse(manifest_dir.exists())

    def test_manifest_is_reduced_to_the_packages_left_installed_without_remove_packages(self):
        # -y alone must not lose the record of the pkg: entries it did not remove,
        # otherwise a later --remove-packages has nothing to work from. Everything
        # already reversed is dropped from the kept manifest.
        manifest_dir = self.prefix / "var" / "lib" / "chaostictool"
        manifest_dir.mkdir(parents=True)
        wrapper = self.mk("usr/local/bin/responder")
        lines = [f"dir:{manifest_dir}", f"file:{wrapper}", "pkg:pacman:wpscan", "pkg:pacman:nmap"]
        result = run_uninstall(self.prefix, lines, remove_packages=0,
                               extra_prelude='pacman() { echo "PACMAN $*" >>"$CALLLOG"; }\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(wrapper.exists())
        self.assertFalse((self.prefix / "calls.log").exists(), "no package manager without --remove-packages")
        self.assertTrue(manifest_dir.exists(), "the manifest dir must survive while packages remain")
        self.assertIn("2 package(s) still installed; re-run with --remove-packages", result.stdout)
        kept = [l for l in (self.prefix / "manifest").read_text().splitlines()
                if l and not l.startswith("#")]
        self.assertEqual(kept, ["pkg:pacman:wpscan", "pkg:pacman:nmap"])
        # A second pass with --remove-packages still finds exactly those packages.
        (self.prefix / "var" / "lib" / "chaostictool").mkdir(parents=True, exist_ok=True)
        result = run_uninstall(self.prefix, kept, remove_packages=1,
                               extra_prelude='pacman() { echo "PACMAN $*" >>"$CALLLOG"; }\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PACMAN -Rns --noconfirm -- wpscan nmap", (self.prefix / "calls.log").read_text())
        self.assertFalse(manifest_dir.exists(), "nothing left to reverse: the manifest goes")

    def test_dry_run_without_remove_packages_only_announces_the_kept_manifest(self):
        manifest_dir = self.prefix / "var" / "lib" / "chaostictool"
        manifest_dir.mkdir(parents=True)
        lines = [f"dir:{manifest_dir}", "pkg:apt:nmap"]
        result = run_uninstall(self.prefix, lines, remove_packages=0, dry_run=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would keep manifest (1 package(s) still installed)", result.stdout)
        self.assertNotIn("would remove dir: " + str(manifest_dir), result.stdout)
        self.assertEqual((self.prefix / "manifest").read_text(),
                         "# ChaosticTool manifest\n" + "\n".join(lines) + "\n",
                         "a dry run must not rewrite the manifest")

    def test_manifest_dir_entry_alone_does_not_list_a_source_checkout(self):
        manifest_dir = self.prefix / "var" / "lib" / "chaostictool"
        manifest_dir.mkdir(parents=True)
        result = run_uninstall(self.prefix, [f"dir:{manifest_dir}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No source directories recorded.", result.stdout)
        self.assertFalse(manifest_dir.exists())

    @unittest.skipIf(os.geteuid() == 0, "root can always remove the locked fixture")
    def test_manifest_dir_is_kept_when_a_removal_failed(self):
        manifest_dir = self.prefix / "var" / "lib" / "chaostictool"
        manifest_dir.mkdir(parents=True)
        locked = self.prefix / "locked"
        locked.mkdir()
        victim = locked / "tool"
        victim.write_text("x")
        locked.chmod(0o555)
        try:
            result = run_uninstall(self.prefix, [f"file:{victim}"])
        finally:
            locked.chmod(0o755)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("could not remove", result.stdout)
        self.assertTrue(victim.exists())
        self.assertTrue(manifest_dir.exists(),
                        "the manifest must survive a failed run so it can be retried")
        self.assertIn("kept (some removals failed", result.stdout)


class DetectionModeGateTests(unittest.TestCase):
    """Without a manifest nothing is removed unless --force-detect is explicit."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.prefix = Path(self.temp.name)
        self.go_bin = self.prefix / "go" / "bin" / "subfinder"
        self.go_bin.parent.mkdir(parents=True)
        self.go_bin.write_text("bin")

    def tearDown(self):
        self.temp.cleanup()

    def test_yes_alone_never_enters_detection_mode(self):
        result = run_detection(self.prefix, assume_yes=1, force_detect=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("requires --force-detect", result.stdout)
        self.assertFalse((self.prefix / "calls.log").exists(),
                         "--yes alone attempted a heuristic removal")
        self.assertTrue(self.go_bin.exists())

    def test_yes_with_dry_run_still_does_not_enter_detection_mode(self):
        result = run_detection(self.prefix, assume_yes=1, force_detect=0, dry_run=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("requires --force-detect", result.stdout)
        self.assertFalse((self.prefix / "calls.log").exists())

    def test_force_detect_with_yes_runs_the_heuristic_removals(self):
        result = run_detection(self.prefix, assume_yes=1, force_detect=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = (self.prefix / "calls.log").read_text()
        self.assertIn("RM_FILE /usr/local/bin/chaostictool", calls)
        self.assertIn("RM_DIR /opt/chaostictool", calls)
        self.assertIn(f"RM_FILE {self.go_bin}", calls, "detected Go binary approved by -y")

    def test_dry_run_summary_says_would_remove_and_omits_the_checkout_note(self):
        result = run_detection(self.prefix, assume_yes=1, force_detect=1, dry_run=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Would remove :", result.stdout)
        self.assertNotIn("Removed :", result.stdout)
        # SCRIPT_DIR holds no uninstall.sh here (packaged command): no checkout note.
        self.assertNotIn("The project directory was not touched", result.stdout)
        self.assertIn("removed with your package manager", result.stdout)
        # An absent wrapper is reported as absent, not as a foreign wrapper.
        self.assertIn("not present: responder", result.stdout)
        self.assertNotIn("not a ChaosticTool wrapper: responder", result.stdout)

    def test_force_detect_without_yes_is_not_approved_non_interactively(self):
        result = run_detection(self.prefix, assume_yes=0, force_detect=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Aborted.", result.stdout)
        self.assertFalse((self.prefix / "calls.log").exists())

    def test_detect_confirm_refuses_yes_without_force_detect(self):
        # Defence in depth: even if a detection step were reached some other way,
        # its approval helper must not treat -y as consent.
        harness = ("set -e\nGREEN=''; RED=''; CYAN=''; YELLOW=''; DIM=''; NC=''\n"
                   "DRY_RUN=0\nASSUME_YES=1\nFORCE_DETECT=0\nORIG_USER=''\nORIG_HOME=/nonexistent\n"
                   "REMOVED=0; SKIPPED=0; FAILED=0\n" + HELPERS + DETECT +
                   'if _detect_confirm "x"; then echo APPROVED; else echo REFUSED; fi\n')
        result = subprocess.run(["bash", "-c", harness], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertNotIn("APPROVED", result.stdout)


class UninstallCliTests(unittest.TestCase):
    """Argument handling that runs before the root gate (safe as non-root)."""

    def test_help_exits_zero_and_describes_options(self):
        result = subprocess.run(["bash", str(ROOT / "uninstall.sh"), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--dry-run", result.stdout)
        self.assertIn("--remove-packages", result.stdout)
        self.assertIn("Pre-existing tools are never recorded", result.stdout)
        # The help must describe the behaviour the gate enforces.
        self.assertIn("--force-detect", result.stdout)
        self.assertIn("Never enables the heuristic detection mode on its own", result.stdout)
        self.assertIn("change nothing on disk", result.stdout)

    def test_unknown_option_is_rejected(self):
        result = subprocess.run(["bash", str(ROOT / "uninstall.sh"), "--not-an-option"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
