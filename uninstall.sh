#!/usr/bin/env bash
# ChaosticTool uninstaller — reverses exactly what /var/lib/chaostictool/manifest
# records. Without a manifest it removes nothing unless the heuristic detection
# mode is requested explicitly with --force-detect.
#
# It is shipped by the native packages as `chaostictool-uninstall` and also runs
# from a git checkout as ./uninstall.sh. Package removal (apt/dnf/pacman) never
# runs this automatically — it only prints a notice — so external tools are
# removed only when the user asks, here.
set -Eeuo pipefail

GREEN='\033[1;32m'; RED='\033[1;31m'; CYAN='\033[1;36m'; YELLOW='\033[1;33m'; DIM='\033[2m'; NC='\033[0m'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

MANIFEST_DIR="/var/lib/chaostictool"
MANIFEST="${MANIFEST:-$MANIFEST_DIR/manifest}"

# Only these prefixes may be passed to `rm -rf` for a recorded dir: entry. The
# manifest is root-owned, but a corrupted or hand-edited line must never be able
# to make the uninstaller delete an arbitrary path.
ALLOWED_DIR_PREFIXES=("/opt/chaostictool" "/var/cache/chaostictool" "/var/lib/chaostictool")

ASSUME_YES=0
DRY_RUN=0
REMOVE_PACKAGES=0
FORCE_DETECT=0

usage() {
    cat <<EOF
ChaosticTool uninstaller

Usage:
  sudo chaostictool-uninstall [options]      (installed command)
  sudo ./uninstall.sh [options]              (from a source checkout)

Reverses exactly what ChaosticTool recorded in:
  $MANIFEST

Options:
  -n, --dry-run         Print the full removal plan (every step, no prompts) and
                        change nothing on disk — not even the manifest.
  -y, --yes             Do not prompt for the removals the manifest records
                        (user-local tools, config restores, --remove-packages).
                        Never enables the heuristic detection mode on its own.
      --remove-packages Also remove the distribution packages ChaosticTool installed
                        (dependency-aware: pacman -Rns / apt purge --autoremove /
                        dnf remove + autoremove). Pre-existing packages are never listed,
                        so only packages ChaosticTool added are offered.
      --force-detect    No manifest (pre-v1.3.2 install): run the heuristic detection
                        mode. Required to remove anything without a manifest, even
                        with -y; -y then auto-approves the detected removals. Without
                        it the uninstaller only explains how to proceed and exits.
  -h, --help            Show this help.

Pre-existing tools are never recorded and therefore never removed.
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        -y|--yes) ASSUME_YES=1 ;;
        -n|--dry-run) DRY_RUN=1 ;;
        --remove-packages) REMOVE_PACKAGES=1 ;;
        --force-detect) FORCE_DETECT=1 ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo -e "${RED}[!] Unknown option: $1${NC}" >&2
            usage >&2
            exit 2
            ;;
    esac
    shift
done

echo -e "${CYAN}=== ChaosticTool uninstaller ===${NC}\n"
[ "$DRY_RUN" -eq 1 ] && echo -e "${YELLOW}[*] Dry run: nothing will be changed.${NC}\n"

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[!] This script requires root privileges.${NC}"
    if [ "${BASH_SOURCE[0]}" = "$0" ] && [ -f "$SCRIPT_DIR/uninstall.sh" ]; then
        echo -e "    Re-run with: ${GREEN}sudo ./uninstall.sh${NC}\n"
    else
        echo -e "    Re-run with: ${GREEN}sudo chaostictool-uninstall${NC}\n"
    fi
    exit 1
fi

ORIG_USER="${SUDO_USER:-}"
ORIG_HOME=""
if [ -n "$ORIG_USER" ] && [ "$ORIG_USER" != "root" ]; then
    ORIG_HOME="$(getent passwd "$ORIG_USER" 2>/dev/null | cut -d: -f6 || true)"
fi
[ -z "$ORIG_HOME" ] && ORIG_HOME="/root"

REMOVED=0
SKIPPED=0
FAILED=0

# A prompt the user can answer; never aborts under `set -e`. When stdin is not a
# terminal and --yes was not given, an optional destructive step is skipped
# rather than guessed, so a piped or GUI-launched run cannot leave a half state.
confirm() {
    local prompt="$1"
    # A dry run prints the whole plan: every step is shown, none is executed
    # (each removal helper below checks DRY_RUN itself before touching disk).
    [ "$DRY_RUN" = "1" ] && return 0
    [ "$ASSUME_YES" = "1" ] && return 0
    if [ ! -t 0 ]; then
        echo -e "  ${DIM}[-] non-interactive and no --yes: skipping optional step.${NC}"
        return 1
    fi
    echo -en "${YELLOW}${prompt} [y/N]${NC} "
    local rep=""
    read -r rep || return 1
    case "${rep,,}" in
        y|yes|o|oui) return 0 ;;
        *) return 1 ;;
    esac
}

# Counts and closing note shared by both modes. A dry run only plans the
# removals it counted, and the "project directory" note is only meaningful
# when running from a source checkout (the packaged command lives in /usr/bin).
_print_summary() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo -e "  Would remove : ${GREEN}${REMOVED}${NC}"
        echo -e "  Skipped      : ${DIM}${SKIPPED}${NC}"
    else
        echo -e "  Removed : ${GREEN}${REMOVED}${NC}"
        echo -e "  Skipped : ${DIM}${SKIPPED}${NC}"
    fi
    [ "$FAILED" -gt 0 ] && echo -e "  Failed  : ${RED}${FAILED}${NC}"
    echo ""
    if [ "${BASH_SOURCE[0]:-}" = "$0" ] && [ -f "$SCRIPT_DIR/uninstall.sh" ] && [ -f "$SCRIPT_DIR/install.sh" ]; then
        echo -e "${DIM}The project directory was not touched: ${SCRIPT_DIR}${NC}"
        echo -e "${DIM}To fully remove it: sudo rm -rf ${SCRIPT_DIR}${NC}"
    else
        echo -e "${DIM}The ChaosticTool package itself is removed with your package manager.${NC}"
    fi
}

_rm_file() {
    local path="$1"
    if [ -e "$path" ] || [ -L "$path" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            echo -e "  ${CYAN}[~] would remove:${NC} $path"
            REMOVED=$((REMOVED + 1))
            return 0
        fi
        if rm -f -- "$path"; then
            echo -e "  ${GREEN}[+] removed:${NC} $path"
            REMOVED=$((REMOVED + 1))
        else
            echo -e "  ${RED}[x] could not remove:${NC} $path"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "  ${DIM}[-] not found: $path${NC}"
        SKIPPED=$((SKIPPED + 1))
    fi
}

_dir_allowed() {
    local path="$1" prefix
    for prefix in "${ALLOWED_DIR_PREFIXES[@]}"; do
        [ "$path" = "$prefix" ] && return 0
        case "$path" in "$prefix"/*) return 0 ;; esac
    done
    return 1
}

_rm_dir() {
    local path="$1"
    if ! _dir_allowed "$path"; then
        echo -e "  ${YELLOW}[!] refusing to remove unexpected directory (not under a ChaosticTool prefix):${NC} $path"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi
    if [ -d "$path" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            echo -e "  ${CYAN}[~] would remove dir:${NC} $path"
            REMOVED=$((REMOVED + 1))
            return 0
        fi
        if rm -rf -- "$path"; then
            echo -e "  ${GREEN}[+] removed dir:${NC} $path"
            REMOVED=$((REMOVED + 1))
        else
            echo -e "  ${RED}[x] could not remove dir:${NC} $path"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "  ${DIM}[-] not found: $path${NC}"
        SKIPPED=$((SKIPPED + 1))
    fi
}

# Run pipx for the original user, matching the install environment exactly, with
# a sudo-free fallback so minimal images without the sudo binary still work.
_pipx_uninstall() {
    local pkg="$1"
    local home="$ORIG_HOME"
    local pipx_env=(PIPX_HOME="$home/.local/share/pipx" PIPX_BIN_DIR="$home/.local/bin"
                    HOME="$home" PATH="$home/.local/bin:$PATH")
    if [ -n "$ORIG_USER" ] && [ "$ORIG_USER" != "root" ]; then
        if command -v runuser >/dev/null 2>&1; then
            runuser -u "$ORIG_USER" -- env "${pipx_env[@]}" pipx uninstall "$pkg"
            return $?
        fi
        if command -v sudo >/dev/null 2>&1; then
            sudo -u "$ORIG_USER" env "${pipx_env[@]}" pipx uninstall "$pkg"
            return $?
        fi
    fi
    command -v pipx >/dev/null 2>&1 || return 1
    env "${pipx_env[@]}" pipx uninstall "$pkg"
}

# Reverse a `pip install --user` done for the original user. A pip:PKG line is
# recorded only when ChaosticTool itself installed the package into an empty
# slot (core.installer checks `pip show` first), so a package the user already
# had is never listed here. Best effort: pip may be gone or the user site may
# have been cleaned by hand; a failure is reported, never hidden.
_pip_uninstall() {
    local pkg="$1"
    local home="$ORIG_HOME"
    # PIP_BREAK_SYSTEM_PACKAGES mirrors the --break-system-packages used at install
    # time and is simply ignored by pip versions that predate the flag.
    local pip_env=(HOME="$home" PATH="$home/.local/bin:$PATH" PIP_BREAK_SYSTEM_PACKAGES=1)
    local runner=()
    if [ -n "$ORIG_USER" ] && [ "$ORIG_USER" != "root" ]; then
        if command -v runuser >/dev/null 2>&1; then
            runner=(runuser -u "$ORIG_USER" --)
        elif command -v sudo >/dev/null 2>&1; then
            runner=(sudo -u "$ORIG_USER")
        else
            return 1
        fi
    fi
    command -v python3 >/dev/null 2>&1 || return 1
    # ${arr[@]+...} keeps an empty runner valid under set -u on every bash.
    ${runner[@]+"${runner[@]}"} env "${pip_env[@]}" python3 -m pip uninstall -y "$pkg"
}

# ---------------------------------------------------------------------------
# Detection mode — used when no manifest is present (pre-v1.3.2 installs)
# ---------------------------------------------------------------------------
detect_and_remove() {
    echo -e "${YELLOW}[!] Running in detection mode (no manifest).${NC}"
    echo -e "    Only known ChaosticTool artefacts will be offered for removal.\n"

    echo -e "\n${CYAN}[D1] Launcher${NC}"
    _rm_file /usr/local/bin/chaostictool

    echo -e "\n${CYAN}[D2] Source-install wrappers${NC}"
    for name in responder whatweb xsstrike; do
        path="/usr/local/bin/$name"
        if [ -f "$path" ] && grep -q "opt/chaostictool" "$path" 2>/dev/null; then
            _rm_file "$path"
        elif [ -e "$path" ]; then
            echo -e "  ${DIM}[-] not a ChaosticTool wrapper: $name${NC}"
            SKIPPED=$((SKIPPED + 1))
        else
            echo -e "  ${DIM}[-] not present: $name${NC}"
        fi
    done

    echo -e "\n${CYAN}[D3] Python-module wrappers${NC}"
    for name in secretsdump.py psexec.py GetUserSPNs.py; do
        path="/usr/local/bin/$name"
        if [ -f "$path" ] && grep -q "impacket" "$path" 2>/dev/null; then
            _rm_file "$path"
        elif [ -e "$path" ]; then
            echo -e "  ${DIM}[-] not a ChaosticTool wrapper: $name${NC}"
            SKIPPED=$((SKIPPED + 1))
        else
            echo -e "  ${DIM}[-] not present: $name${NC}"
        fi
    done

    # Legacy PEASS assets from older releases carried a ChaosticTool-owned name.
    # There is no provenance record for them, so they are only offered when they
    # exist and removed only after an explicit approval; _rm_file honours --dry-run.
    echo -e "\n${CYAN}[D4] Legacy direct downloads${NC}"
    local peas_found=()
    for f in /usr/local/bin/linpeas.sh /usr/local/bin/winpeas.exe; do
        [ -f "$f" ] && peas_found+=("$f")
    done
    if [ "${#peas_found[@]}" -gt 0 ]; then
        echo -e "  ${YELLOW}Legacy PEASS files found:${NC}"
        for f in "${peas_found[@]}"; do echo -e "    $f"; done
        if _detect_confirm "  Remove these legacy PEASS files?"; then
            for f in "${peas_found[@]}"; do _rm_file "$f"; done
        else
            SKIPPED=$((SKIPPED + ${#peas_found[@]}))
        fi
    else
        echo -e "  ${DIM}[-] no legacy PEASS files present${NC}"
    fi

    # A symlink into a user-local tool directory is a strong hint, not a proof:
    # list the matches and ask before removing them.
    echo -e "\n${CYAN}[D5] Symlinks to user-local binaries${NC}"
    local link_found=()
    for p in /usr/local/bin/*; do
        [ -L "$p" ] || continue
        target="$(readlink "$p")"
        if echo "$target" | grep -qE "^/(home/[^/]+|root)/(go/bin|\.local/share/go/bin|\.cargo/bin|\.local/bin)/"; then
            link_found+=("$p")
        fi
    done
    if [ "${#link_found[@]}" -gt 0 ]; then
        echo -e "  ${YELLOW}Symlinks into user-local tool directories:${NC}"
        for p in "${link_found[@]}"; do echo -e "    $p -> $(readlink "$p")"; done
        if _detect_confirm "  Remove these symlinks?"; then
            for p in "${link_found[@]}"; do _rm_file "$p"; done
        else
            SKIPPED=$((SKIPPED + ${#link_found[@]}))
        fi
    else
        echo -e "  ${DIM}[-] no matching symlinks${NC}"
    fi

    echo -e "\n${CYAN}[D6] Source checkouts${NC}"
    _rm_dir /opt/chaostictool
    _rm_dir /var/cache/chaostictool

    echo -e "\n${CYAN}[D7] Tor/proxychains config restore${NC}"
    for bak in /etc/tor/torrc.chaostictool.bak \
               /etc/proxychains.conf.chaostictool.bak \
               /etc/proxychains4.conf.chaostictool.bak; do
        if [ -f "$bak" ]; then
            original="${bak%.chaostictool.bak}"
            if [ "$DRY_RUN" -eq 1 ]; then
                echo -e "  ${CYAN}[~] would restore:${NC} $original"
            else
                cp -- "$bak" "$original"
                rm -f -- "$bak"
                echo -e "  ${GREEN}[+] restored:${NC} $original"
            fi
            REMOVED=$((REMOVED + 1))
        fi
    done

    echo -e "\n${CYAN}[D8] User-local tools (Go/Cargo/pipx/gem)${NC}"
    _detect_user_tools
}

# Heuristic removals are destructive without a provenance record: they need the
# explicit --force-detect flag, and -y auto-approves them only alongside it. The
# no-manifest gate below already enforces this; keeping the check here as well
# means no detection step can ever act on -y alone, whatever calls it.
_detect_confirm() {
    local prompt="$1"
    if [ "$FORCE_DETECT" != "1" ]; then
        echo -e "  ${DIM}[-] detection removals require --force-detect (--yes alone never approves them).${NC}"
        return 1
    fi
    confirm "$prompt"
}

_detect_user_tools() {
    local GO_BINS=(subfinder amass httpx nuclei naabu katana gau waybackurls ffuf dalfox gobuster bettercap)
    local go_found=()
    for bin in "${GO_BINS[@]}"; do
        for dir in "$ORIG_HOME/go/bin" "$ORIG_HOME/.local/share/go/bin" "/root/go/bin"; do
            [ -f "$dir/$bin" ] && go_found+=("$dir/$bin")
        done
    done
    if [ "${#go_found[@]}" -gt 0 ]; then
        echo -e "  ${YELLOW}Go binaries found:${NC}"
        for f in "${go_found[@]}"; do echo -e "    $f"; done
        if _detect_confirm "  Remove these Go binaries?"; then
            for f in "${go_found[@]}"; do _rm_file "$f"; done
        fi
    fi

    local CARGO_BINS=(rustscan)
    local cargo_found=()
    for bin in "${CARGO_BINS[@]}"; do
        for dir in "$ORIG_HOME/.cargo/bin" "/root/.cargo/bin"; do
            [ -f "$dir/$bin" ] && cargo_found+=("$dir/$bin")
        done
    done
    if [ "${#cargo_found[@]}" -gt 0 ]; then
        echo -e "  ${YELLOW}Cargo binaries found:${NC}"
        for f in "${cargo_found[@]}"; do echo -e "    $f"; done
        if _detect_confirm "  Remove these Cargo binaries?"; then
            for f in "${cargo_found[@]}"; do _rm_file "$f"; done
        fi
    fi

    local PIPX_NAMES=(theHarvester impacket netexec)
    if command -v pipx >/dev/null 2>&1; then
        local pipx_list
        pipx_list=$(if [ -n "$ORIG_USER" ] && [ "$ORIG_USER" != "root" ] && command -v sudo >/dev/null 2>&1; then
            sudo -u "$ORIG_USER" pipx list 2>/dev/null || true
        else
            pipx list 2>/dev/null || true
        fi)
        local pipx_ours=()
        for pkg in "${PIPX_NAMES[@]}"; do
            echo "$pipx_list" | grep -qi "package $pkg" && pipx_ours+=("$pkg")
        done
        if [ "${#pipx_ours[@]}" -gt 0 ]; then
            echo -e "  ${YELLOW}pipx packages:${NC}"
            for p in "${pipx_ours[@]}"; do echo -e "    $p"; done
            if _detect_confirm "  Uninstall these pipx packages?"; then
                for p in "${pipx_ours[@]}"; do
                    if [ "$DRY_RUN" -eq 1 ]; then
                        echo -e "  ${CYAN}[~] would pipx uninstall:${NC} $p"
                        REMOVED=$((REMOVED + 1))
                    elif _pipx_uninstall "$p" >/dev/null 2>&1; then
                        echo -e "  ${GREEN}[+] pipx uninstalled:${NC} $p"
                        REMOVED=$((REMOVED + 1))
                    else
                        echo -e "  ${RED}[x] pipx uninstall failed:${NC} $p"
                        FAILED=$((FAILED + 1))
                    fi
                done
            fi
        fi
    fi

    if command -v gem >/dev/null 2>&1 && gem list -i wpscan >/dev/null 2>&1; then
        if _detect_confirm "  Uninstall wpscan via gem?"; then
            if [ "$DRY_RUN" -eq 1 ]; then
                echo -e "  ${CYAN}[~] would gem uninstall:${NC} wpscan"
            else
                gem uninstall wpscan --executables --all 2>/dev/null || true
            fi
            REMOVED=$((REMOVED + 1))
        fi
    fi
}

# ---------------------------------------------------------------------------
# No manifest → detection fallback
# ---------------------------------------------------------------------------
if [ ! -f "$MANIFEST" ]; then
    echo -e "${YELLOW}[!] No manifest found at $MANIFEST${NC}"
    echo -e "    This installation predates the manifest system (v1.3.2+)."
    echo ""
    echo -e "  Option 1: re-run ${GREEN}sudo ./install.sh${NC} — it will generate a manifest,"
    echo -e "            then run this script again for a clean removal."
    echo -e "  Option 2: re-run with ${GREEN}--force-detect${NC} — detection mode scans for known"
    echo -e "            ChaosticTool artefacts and offers to remove them (preview with"
    echo -e "            ${GREEN}--dry-run --force-detect${NC}; add ${GREEN}-y${NC} to approve them all)."
    echo ""
    # Detection is heuristic, so it never starts on -y alone: without the explicit
    # --force-detect flag nothing is removed, whatever else was passed.
    if [ "$FORCE_DETECT" != "1" ]; then
        echo -e "${DIM}Nothing was removed: detection mode requires --force-detect.${NC}"
        exit 0
    fi
    if ! confirm "Run detection mode now?"; then
        echo -e "${DIM}Aborted.${NC}"
        exit 0
    fi
    detect_and_remove
    echo -e "\n${CYAN}=== Summary ===${NC}"
    _print_summary
    [ "$FAILED" -gt 0 ] && exit 1
    exit 0
fi

# ---------------------------------------------------------------------------
# Parse manifest into typed arrays
# ---------------------------------------------------------------------------
declare -a M_FILES=()
declare -a M_SYMLINKS=()
declare -a M_DIRS=()
declare -a M_GO=()
declare -a M_CARGO=()
declare -a M_PIPX=()
declare -a M_PIP=()
declare -a M_GEM=()
declare -a M_REPOS=()
declare -a M_PKGS=()
# pkg: entries this run leaves installed (no --remove-packages, declined, or an
# unknown manager): the manifest must keep them so --remove-packages can follow.
declare -a M_PKGS_KEPT=()

while IFS= read -r line; do
    [[ "$line" =~ ^# ]] && continue
    [[ -z "$line" ]] && continue
    case "$line" in
        file:*)        M_FILES+=("${line#file:}") ;;
        symlink:*)     M_SYMLINKS+=("${line#symlink:}") ;;
        # The manifest directory itself is handled by section [7].
        dir:*)         [ "${line#dir:}" = "$MANIFEST_DIR" ] || M_DIRS+=("${line#dir:}") ;;
        go:*)          M_GO+=("${line#go:}") ;;
        cargo:*)       M_CARGO+=("${line#cargo:}") ;;
        pipx:*)        M_PIPX+=("${line#pipx:}") ;;
        pip:*)         M_PIP+=("${line#pip:}") ;;
        gem:*)         M_GEM+=("${line#gem:}") ;;
        repo:*)        M_REPOS+=("${line#repo:}") ;;
        # Backups are restored below, then removed. Never delete them as files.
        torrc:*|proxychains:*) ;;
        pkg:*)         M_PKGS+=("${line#pkg:}") ;;
    esac
done < "$MANIFEST"

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[1] Files installed by ChaosticTool${NC}"

APT_SOURCES_REMOVED=0

if [ "${#M_FILES[@]}" -gt 0 ]; then
    for path in "${M_FILES[@]}"; do
        _rm_file "$path"
        # Track if an apt sources list was removed (to refresh later)
        [[ "$path" == /etc/apt/sources.list.d/*.list ]] && APT_SOURCES_REMOVED=1 || true
    done
else
    echo -e "  ${DIM}No files recorded.${NC}"
fi

# Restore Tor/proxychains from backups
for bak in /etc/tor/torrc.chaostictool.bak \
           /etc/proxychains.conf.chaostictool.bak \
           /etc/proxychains4.conf.chaostictool.bak; do
    [ -f "$bak" ] || continue
    original="${bak%.chaostictool.bak}"
    if [ "${DRY_RUN:-0}" -eq 1 ]; then
        echo -e "  ${CYAN}[~] would restore:${NC} $original"
    else
        cp -- "$bak" "$original"
        rm -f -- "$bak"
        echo -e "  ${GREEN}[+] restored:${NC} $original"
    fi
    REMOVED=$((REMOVED + 1))
done

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[2] Symlinks to user-local binaries${NC}"
if [ "${#M_SYMLINKS[@]}" -gt 0 ]; then
    for path in "${M_SYMLINKS[@]}"; do
        _rm_file "$path"
    done
else
    echo -e "  ${DIM}No symlinks recorded.${NC}"
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[3] Source checkouts and staging directories${NC}"
if [ "${#M_DIRS[@]}" -gt 0 ]; then
    for path in "${M_DIRS[@]}"; do
        [ "$path" = "$MANIFEST_DIR" ] && continue
        _rm_dir "$path"
    done
else
    echo -e "  ${DIM}No source directories recorded.${NC}"
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[4] Extra package sources${NC}"
if [ "${#M_REPOS[@]}" -gt 0 ]; then
    for entry in "${M_REPOS[@]}"; do
        # Format: pm:conftype:path  e.g. pacman:/etc/pacman.conf:chaotic-aur
        local_pm="${entry%%:*}"
        rest="${entry#*:}"
        repo_path="${rest%%:*}"
        repo_id="${rest#*:}"
        if [ "$local_pm" = "pacman" ] && [ -f "$repo_path" ]; then
            if [ "$DRY_RUN" -eq 1 ]; then
                echo -e "  ${CYAN}[~] would remove repo section:${NC} [${repo_id}] from $repo_path"
            else
                # Bounded delete: remove the [id] header and its Include line only,
                # stopping at the next section header, so a user section appended
                # after ours (no blank line between) is never swallowed.
                if python3 - "$repo_path" "$repo_id" <<'PY'
import re, sys
path, repo_id = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8", errors="surrogateescape") as handle:
    lines = handle.readlines()
out, drop = [], False
for line in lines:
    stripped = line.strip()
    if stripped == f"[{repo_id}]":
        drop = True
        continue
    if drop:
        if stripped.startswith("[") and stripped.endswith("]"):
            drop = False            # next section begins; keep it
        elif stripped == "" or stripped.lower().startswith("include"):
            continue                # our own block body
        else:
            drop = False            # unexpected line; stop dropping, keep it
    out.append(line)
text = "".join(out)
while "\n\n\n" in text:
    text = text.replace("\n\n\n", "\n\n")
with open(path, "w", encoding="utf-8", errors="surrogateescape") as handle:
    handle.write(text)
PY
                then
                    echo -e "  ${GREEN}[+] removed repo section:${NC} [${repo_id}] from $repo_path"
                    # Drop the now-orphaned sync database so pacman does not warn.
                    rm -f -- "/var/lib/pacman/sync/${repo_id}.db" 2>/dev/null || true
                else
                    echo -e "  ${RED}[x] could not edit repo section [${repo_id}] in $repo_path${NC}"
                    FAILED=$((FAILED + 1))
                fi
            fi
            REMOVED=$((REMOVED + 1))
        fi
    done
else
    echo -e "  ${DIM}No extra sources recorded.${NC}"
fi

# Refresh package index if apt sources were removed
if [ "$APT_SOURCES_REMOVED" -eq 1 ] && [ "$DRY_RUN" -eq 0 ] && command -v apt >/dev/null 2>&1; then
    echo -e "  ${CYAN}[*] Refreshing apt after source removal${NC}"
    apt update -qq 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[5] User-local tools (Go, Cargo, pipx, pip, gem)${NC}"

if [ "${#M_GO[@]}" -gt 0 ]; then
    echo -e "  ${YELLOW}Go binaries installed by ChaosticTool:${NC}"
    for path in "${M_GO[@]}"; do echo -e "    $path"; done
    if confirm "  Remove these Go binaries?"; then
        for path in "${M_GO[@]}"; do _rm_file "$path"; done
    else
        SKIPPED=$((SKIPPED + ${#M_GO[@]}))
    fi
else
    echo -e "  ${DIM}No Go binaries recorded.${NC}"
fi

if [ "${#M_CARGO[@]}" -gt 0 ]; then
    echo -e "  ${YELLOW}Cargo binaries installed by ChaosticTool:${NC}"
    for path in "${M_CARGO[@]}"; do echo -e "    $path"; done
    if confirm "  Remove these Cargo binaries?"; then
        for path in "${M_CARGO[@]}"; do _rm_file "$path"; done
    else
        SKIPPED=$((SKIPPED + ${#M_CARGO[@]}))
    fi
else
    echo -e "  ${DIM}No Cargo binaries recorded.${NC}"
fi

if [ "${#M_PIPX[@]}" -gt 0 ]; then
    echo -e "  ${YELLOW}pipx packages installed by ChaosticTool:${NC}"
    for pkg in "${M_PIPX[@]}"; do echo -e "    $pkg"; done
    if confirm "  Uninstall these pipx packages?"; then
        for pkg in "${M_PIPX[@]}"; do
            if [ "$DRY_RUN" -eq 1 ]; then
                echo -e "  ${CYAN}[~] would pipx uninstall:${NC} $pkg"
                REMOVED=$((REMOVED + 1))
            elif _pipx_uninstall "$pkg" >/dev/null 2>&1; then
                echo -e "  ${GREEN}[+] pipx uninstalled:${NC} $pkg"
                REMOVED=$((REMOVED + 1))
            else
                echo -e "  ${RED}[x] pipx uninstall failed:${NC} $pkg"
                FAILED=$((FAILED + 1))
            fi
        done
    else
        SKIPPED=$((SKIPPED + ${#M_PIPX[@]}))
    fi
else
    echo -e "  ${DIM}No pipx packages recorded.${NC}"
fi

if [ "${#M_PIP[@]}" -gt 0 ]; then
    echo -e "  ${YELLOW}pip --user packages installed by ChaosticTool:${NC}"
    for pkg in "${M_PIP[@]}"; do echo -e "    $pkg"; done
    if confirm "  Uninstall these pip packages?"; then
        for pkg in "${M_PIP[@]}"; do
            if [ "$DRY_RUN" -eq 1 ]; then
                echo -e "  ${CYAN}[~] would pip uninstall:${NC} $pkg"
                REMOVED=$((REMOVED + 1))
            elif _pip_uninstall "$pkg" >/dev/null 2>&1; then
                echo -e "  ${GREEN}[+] pip uninstalled:${NC} $pkg"
                REMOVED=$((REMOVED + 1))
            else
                echo -e "  ${RED}[x] pip uninstall failed (best effort):${NC} $pkg"
                echo -e "  ${DIM}    remove it by hand: python3 -m pip uninstall $pkg${NC}"
                FAILED=$((FAILED + 1))
            fi
        done
    else
        SKIPPED=$((SKIPPED + ${#M_PIP[@]}))
    fi
else
    echo -e "  ${DIM}No pip packages recorded.${NC}"
fi

if [ "${#M_GEM[@]}" -gt 0 ]; then
    echo -e "  ${YELLOW}gem packages installed by ChaosticTool:${NC}"
    for pkg in "${M_GEM[@]}"; do echo -e "    $pkg"; done
    if confirm "  Uninstall these gem packages?"; then
        for pkg in "${M_GEM[@]}"; do
            if ! command -v gem >/dev/null 2>&1; then
                echo -e "  ${DIM}[-] gem not available: $pkg${NC}"
                SKIPPED=$((SKIPPED + 1))
            elif [ "$DRY_RUN" -eq 1 ]; then
                echo -e "  ${CYAN}[~] would gem uninstall:${NC} $pkg"
                REMOVED=$((REMOVED + 1))
            elif gem uninstall "$pkg" --executables --all 2>/dev/null; then
                echo -e "  ${GREEN}[+] gem uninstalled:${NC} $pkg"
                REMOVED=$((REMOVED + 1))
            else
                echo -e "  ${RED}[x] gem uninstall failed:${NC} $pkg"
                FAILED=$((FAILED + 1))
            fi
        done
    else
        SKIPPED=$((SKIPPED + ${#M_GEM[@]}))
    fi
else
    echo -e "  ${DIM}No gem packages recorded.${NC}"
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[6] System packages${NC}"
if [ "${#M_PKGS[@]}" -gt 0 ]; then
    declare -A by_pm=()
    for entry in "${M_PKGS[@]}"; do
        pm="${entry%%:*}"
        pkg="${entry#*:}"
        by_pm["$pm"]+=" $pkg"
    done
    # Every pkg: line is a package ChaosticTool installed because it was ABSENT
    # before (both installers filter out already-present packages), so an
    # automatic removal here cannot touch a pre-existing system tool.
    if [ "$REMOVE_PACKAGES" -eq 1 ]; then
        echo -e "  ${YELLOW}Removing distribution packages ChaosticTool installed:${NC}"
        for pm in "${!by_pm[@]}"; do
            read -r -a pkgs <<< "${by_pm[$pm]}"
            [ "${#pkgs[@]}" -gt 0 ] || continue
            case "$pm" in
                pacman) cmd=(pacman -Rns --noconfirm -- "${pkgs[@]}") ;;
                apt)    cmd=(apt-get purge -y --autoremove -- "${pkgs[@]}") ;;
                dnf)    cmd=(dnf remove -y "${pkgs[@]}") ;;
                zypper) cmd=(zypper --non-interactive rm --clean-deps "${pkgs[@]}") ;;
                apk)    cmd=(apk del "${pkgs[@]}") ;;
                *)      echo -e "  ${DIM}unknown manager $pm: ${pkgs[*]}${NC}"
                        for pkg in "${pkgs[@]}"; do M_PKGS_KEPT+=("$pm:$pkg"); done
                        continue ;;
            esac
            echo -e "  ${DIM}\$ ${cmd[*]}${NC}"
            if [ "$DRY_RUN" -eq 1 ]; then
                continue
            fi
            if confirm "  Run the command above?"; then
                if "${cmd[@]}"; then
                    if [ "$pm" = "dnf" ]; then
                        dnf autoremove -y >/dev/null 2>&1 || true
                    fi
                    REMOVED=$((REMOVED + ${#pkgs[@]}))
                else
                    echo -e "  ${RED}[x] package removal reported an error for $pm${NC}"
                    FAILED=$((FAILED + 1))
                fi
            else
                SKIPPED=$((SKIPPED + ${#pkgs[@]}))
                for pkg in "${pkgs[@]}"; do M_PKGS_KEPT+=("$pm:$pkg"); done
            fi
        done
    else
        M_PKGS_KEPT=("${M_PKGS[@]}")
        echo -e "  ${DIM}These packages were installed by ChaosticTool. Re-run with --remove-packages${NC}"
        echo -e "  ${DIM}to remove them automatically (dependency-aware), or remove manually:${NC}\n"
        for pm in "${!by_pm[@]}"; do
            pkglist="${by_pm[$pm]}"
            case "$pm" in
                pacman) echo -e "  ${DIM}sudo pacman -Rns${pkglist}${NC}" ;;
                apt)    echo -e "  ${DIM}sudo apt-get purge --autoremove${pkglist}${NC}" ;;
                dnf)    echo -e "  ${DIM}sudo dnf remove${pkglist} && sudo dnf autoremove${NC}" ;;
                zypper) echo -e "  ${DIM}sudo zypper rm --clean-deps${pkglist}${NC}" ;;
                apk)    echo -e "  ${DIM}sudo apk del${pkglist}${NC}" ;;
                *)      echo -e "  ${DIM}${pm} remove${pkglist}${NC}" ;;
            esac
        done
    fi
else
    echo -e "  ${DIM}No system packages recorded.${NC}"
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[7] Manifest directory${NC}"
# The record is the only way to retry, so it is kept when a step failed. _rm_dir
# honours --dry-run itself, so a dry run never loses the manifest either.
# When packages stay installed, the manifest is reduced to those pkg: lines so a
# later --remove-packages still knows what to remove; nothing else is left to
# reverse, so the lines already handled are dropped.
if [ "$FAILED" -gt 0 ]; then
    echo -e "  ${YELLOW}[!] kept (some removals failed; fix them and re-run):${NC} $MANIFEST_DIR"
elif [ "${#M_PKGS_KEPT[@]}" -gt 0 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        echo -e "  ${CYAN}[~] would keep manifest (${#M_PKGS_KEPT[@]} package(s) still installed):${NC} $MANIFEST"
    else
        {
            echo "# ChaosticTool manifest"
            echo "# reduced by the uninstaller: packages still installed (use --remove-packages)"
            for entry in "${M_PKGS_KEPT[@]}"; do echo "pkg:$entry"; done
        } > "$MANIFEST"
        echo -e "  ${YELLOW}[!] kept (${#M_PKGS_KEPT[@]} package(s) still installed; re-run with --remove-packages):${NC} $MANIFEST"
    fi
else
    _rm_dir "$MANIFEST_DIR"
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}=== Summary ===${NC}"
_print_summary

[ "$FAILED" -gt 0 ] && exit 1
exit 0
