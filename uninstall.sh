#!/usr/bin/env bash
# ChaosticTool uninstaller
set -Eeuo pipefail

GREEN='\033[1;32m'; RED='\033[1;31m'; CYAN='\033[1;36m'; YELLOW='\033[1;33m'; DIM='\033[2m'; NC='\033[0m'
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}=== ChaosticTool uninstaller ===${NC}\n"

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}[!] This script requires root privileges.${NC}"
    echo -e "    Re-run with: ${GREEN}sudo ./uninstall.sh${NC}\n"
    exit 1
fi

ORIG_USER="${SUDO_USER:-}"
ORIG_HOME=""
if [ -n "$ORIG_USER" ] && [ "$ORIG_USER" != "root" ]; then
    ORIG_HOME="$(getent passwd "$ORIG_USER" 2>/dev/null | cut -d: -f6 || true)"
fi
[ -z "$ORIG_HOME" ] && ORIG_HOME="/root"

confirm() {
    local prompt="$1"
    echo -en "${YELLOW}${prompt} [y/N]${NC} "
    read -r rep
    case "${rep,,}" in
        y|yes|o|oui) return 0 ;;
        *) return 1 ;;
    esac
}

REMOVED=0
SKIPPED=0

_rm_file() {
    local path="$1" desc="${2:-$1}"
    if [ -e "$path" ] || [ -L "$path" ]; then
        rm -f "$path"
        echo -e "  ${GREEN}[+] removed:${NC} $desc"
        REMOVED=$((REMOVED + 1))
    else
        echo -e "  ${DIM}[-] not found: $desc${NC}"
        SKIPPED=$((SKIPPED + 1))
    fi
}

_rm_dir() {
    local path="$1" desc="${2:-$1}"
    if [ -d "$path" ]; then
        rm -rf "$path"
        echo -e "  ${GREEN}[+] removed:${NC} $desc"
        REMOVED=$((REMOVED + 1))
    else
        echo -e "  ${DIM}[-] not found: $desc${NC}"
        SKIPPED=$((SKIPPED + 1))
    fi
}

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[1/9] Launcher${NC}"
_rm_file /usr/local/bin/chaostictool

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[2/9] Source-install wrappers (/usr/local/bin → /opt/chaostictool/)${NC}"
# Wrappers written by _install_source_tool contain the /opt/chaostictool/ path
for name in responder whatweb xsstrike; do
    path="/usr/local/bin/$name"
    if [ -f "$path" ] && grep -q "opt/chaostictool" "$path" 2>/dev/null; then
        _rm_file "$path"
    else
        echo -e "  ${DIM}[-] not a ChaosticTool wrapper: $name${NC}"
        SKIPPED=$((SKIPPED + 1))
    fi
done

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[3/9] Python-module wrappers (impacket scripts)${NC}"
# Wrappers written by _install_python_module_wrapper contain "impacket" in exec line
for name in secretsdump.py psexec.py GetUserSPNs.py; do
    path="/usr/local/bin/$name"
    if [ -f "$path" ] && grep -q "impacket" "$path" 2>/dev/null; then
        _rm_file "$path"
    else
        echo -e "  ${DIM}[-] not a ChaosticTool wrapper: $name${NC}"
        SKIPPED=$((SKIPPED + 1))
    fi
done

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[4/9] Direct downloads (PEASS assets, release binaries)${NC}"
_rm_file /usr/local/bin/linpeas.sh
_rm_file /usr/local/bin/winpeas.exe
# rustscan release asset: only remove if it is a plain file (not a symlink to a user install)
if [ -f /usr/local/bin/rustscan ] && [ ! -L /usr/local/bin/rustscan ]; then
    _rm_file /usr/local/bin/rustscan
else
    echo -e "  ${DIM}[-] rustscan is a symlink or absent — handled in step 5${NC}"
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[5/9] Symlinks to user-local binaries (go/bin, .cargo/bin, .local/bin)${NC}"
# Every binary the installer might have symlinked into /usr/local/bin
ALL_TOOL_BINS=(
    whois dig subfinder amass dnsrecon theHarvester shodan
    nmap rustscan masscan naabu
    gobuster ffuf httpx httpx-toolkit wafw00f whatweb katana gau waybackurls
    nikto nuclei wpscan testssl testssl.sh sslscan
    sqlmap xsstrike dalfox msfconsole msfvenom
    linpeas.sh winpeas.exe secretsdump.py psexec.py GetUserSPNs.py
    crackmapexec nxc bloodhound-python
    hashcat john hydra
    airmon-ng airodump-ng aircrack-ng reaver wifite
    bettercap ettercap tcpdump responder
    proxychains4 proxychains
)

for bin in "${ALL_TOOL_BINS[@]}"; do
    p="/usr/local/bin/$bin"
    if [ -L "$p" ]; then
        target="$(readlink "$p")"
        # Remove only if the symlink points to a user-local tool dir
        if echo "$target" | grep -qE "^/(home/[^/]+|root)/(go/bin|\.local/share/go/bin|\.cargo/bin|\.local/bin)/"; then
            _rm_file "$p" "symlink $bin → $target"
        else
            echo -e "  ${DIM}[-] symlink target not user-local, skipping: $bin → $target${NC}"
            SKIPPED=$((SKIPPED + 1))
        fi
    fi
done

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[6/9] Source checkouts and staging directories${NC}"
_rm_dir /opt/chaostictool
_rm_dir /var/cache/chaostictool

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[7/9] Restoring Tor and proxychains configurations${NC}"
for bak in /etc/tor/torrc.chaostictool.bak \
           /etc/proxychains.conf.chaostictool.bak \
           /etc/proxychains4.conf.chaostictool.bak; do
    if [ -f "$bak" ]; then
        original="${bak%.chaostictool.bak}"
        cp -- "$bak" "$original"
        rm -f "$bak"
        echo -e "  ${GREEN}[+] restored:${NC} $original"
        REMOVED=$((REMOVED + 1))
    else
        echo -e "  ${DIM}[-] no backup: $bak${NC}"
        SKIPPED=$((SKIPPED + 1))
    fi
done

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[8/9] User-local tools (Go, Cargo, pipx, gem)${NC}"

# --- Go binaries ---
GO_BINS=(subfinder amass httpx nuclei naabu katana gau waybackurls ffuf dalfox gobuster bettercap)
go_found=()
for bin in "${GO_BINS[@]}"; do
    for dir in \
        "$ORIG_HOME/go/bin" \
        "$ORIG_HOME/.local/share/go/bin" \
        "/root/go/bin" \
        "/root/.local/share/go/bin"
    do
        [ -f "$dir/$bin" ] && go_found+=("$dir/$bin")
    done
done

if [ "${#go_found[@]}" -gt 0 ]; then
    echo -e "  ${YELLOW}Go-installed binaries found:${NC}"
    for f in "${go_found[@]}"; do echo -e "    $f"; done
    if confirm "  Remove these Go binaries?"; then
        for f in "${go_found[@]}"; do
            rm -f "$f"
            echo -e "  ${GREEN}[+] removed:${NC} $f"
            REMOVED=$((REMOVED + 1))
        done
    fi
else
    echo -e "  ${DIM}No Go-installed binaries found.${NC}"
fi

# --- Cargo binaries ---
CARGO_BINS=(rustscan)
cargo_found=()
for bin in "${CARGO_BINS[@]}"; do
    for dir in "$ORIG_HOME/.cargo/bin" "/root/.cargo/bin"; do
        [ -f "$dir/$bin" ] && cargo_found+=("$dir/$bin")
    done
done

if [ "${#cargo_found[@]}" -gt 0 ]; then
    echo -e "  ${YELLOW}Cargo-installed binaries found:${NC}"
    for f in "${cargo_found[@]}"; do echo -e "    $f"; done
    if confirm "  Remove these Cargo binaries?"; then
        for f in "${cargo_found[@]}"; do
            rm -f "$f"
            echo -e "  ${GREEN}[+] removed:${NC} $f"
            REMOVED=$((REMOVED + 1))
        done
    fi
else
    echo -e "  ${DIM}No Cargo-installed binaries found.${NC}"
fi

# --- pipx packages (run as original user) ---
PIPX_NAMES=(theHarvester impacket netexec)
if [ -n "$ORIG_USER" ] && [ "$ORIG_USER" != "root" ] && command -v pipx >/dev/null 2>&1; then
    pipx_list=$(sudo -u "$ORIG_USER" pipx list 2>/dev/null || true)
    pipx_ours=()
    for pkg in "${PIPX_NAMES[@]}"; do
        if echo "$pipx_list" | grep -qi "package $pkg"; then
            pipx_ours+=("$pkg")
        fi
    done
    if [ "${#pipx_ours[@]}" -gt 0 ]; then
        echo -e "  ${YELLOW}pipx packages (user: $ORIG_USER):${NC}"
        for p in "${pipx_ours[@]}"; do echo -e "    $p"; done
        if confirm "  Uninstall these pipx packages?"; then
            for p in "${pipx_ours[@]}"; do
                sudo -u "$ORIG_USER" pipx uninstall "$p" || true
                echo -e "  ${GREEN}[+] pipx uninstalled:${NC} $p"
                REMOVED=$((REMOVED + 1))
            done
        fi
    else
        echo -e "  ${DIM}No matching pipx packages found.${NC}"
    fi
elif command -v pipx >/dev/null 2>&1; then
    pipx_list=$(pipx list 2>/dev/null || true)
    pipx_ours=()
    for pkg in "${PIPX_NAMES[@]}"; do
        echo "$pipx_list" | grep -qi "package $pkg" && pipx_ours+=("$pkg")
    done
    if [ "${#pipx_ours[@]}" -gt 0 ]; then
        echo -e "  ${YELLOW}pipx packages found:${NC}"
        for p in "${pipx_ours[@]}"; do echo -e "    $p"; done
        if confirm "  Uninstall these pipx packages?"; then
            for p in "${pipx_ours[@]}"; do
                pipx uninstall "$p" || true
                REMOVED=$((REMOVED + 1))
            done
        fi
    else
        echo -e "  ${DIM}No matching pipx packages found.${NC}"
    fi
else
    echo -e "  ${DIM}pipx not found — skipping.${NC}"
fi

# --- gem packages (installed as root by the installer) ---
if command -v gem >/dev/null 2>&1; then
    if gem list wpscan 2>/dev/null | grep -q wpscan; then
        echo -e "  ${YELLOW}gem package found: wpscan${NC}"
        if confirm "  Uninstall wpscan via gem?"; then
            gem uninstall wpscan --executables --all 2>/dev/null || true
            echo -e "  ${GREEN}[+] gem uninstalled:${NC} wpscan"
            REMOVED=$((REMOVED + 1))
        fi
    else
        echo -e "  ${DIM}wpscan gem not installed.${NC}"
    fi
else
    echo -e "  ${DIM}gem not found — skipping.${NC}"
fi

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}[9/9] System packages — review manually${NC}"
echo -e "  ${DIM}These packages may have been installed by ChaosticTool. Only remove${NC}"
echo -e "  ${DIM}what you no longer need:${NC}\n"

detect_pm() {
    command -v pacman >/dev/null 2>&1 && echo pacman && return
    command -v apt    >/dev/null 2>&1 && echo apt    && return
    command -v dnf    >/dev/null 2>&1 && echo dnf    && return
    echo ""
}
PM="$(detect_pm)"

case "$PM" in
    pacman)
        echo -e "  ${DIM}sudo pacman -Rs whois bind nmap masscan gobuster wafw00f nikto testssl.sh sslscan sqlmap hashcat john hydra aircrack-ng tcpdump python-impacket${NC}"
        echo -e "  ${DIM}sudo pacman -Rs tor proxychains-ng  # only if Tor was configured${NC}"
        ;;
    apt)
        echo -e "  ${DIM}sudo apt remove --autoremove whois dnsutils nmap masscan gobuster wafw00f whatweb nikto sslscan sqlmap python3-impacket hashcat john hydra aircrack-ng tcpdump${NC}"
        echo -e "  ${DIM}sudo apt remove --autoremove tor proxychains4  # only if Tor was configured${NC}"
        ;;
    dnf)
        echo -e "  ${DIM}sudo dnf remove whois bind-utils nmap masscan nikto sslscan sqlmap hashcat john hydra aircrack-ng tcpdump${NC}"
        echo -e "  ${DIM}sudo dnf remove tor proxychains-ng  # only if Tor was configured${NC}"
        ;;
    *)
        echo -e "  ${DIM}(package manager not detected — remove manually)${NC}"
        ;;
esac

# ---------------------------------------------------------------------------
echo -e "\n${CYAN}=== Summary ===${NC}"
echo -e "  Removed : ${GREEN}${REMOVED}${NC}"
echo -e "  Skipped : ${DIM}${SKIPPED}${NC}"
echo ""
echo -e "${DIM}The project directory was not touched: ${SCRIPT_DIR}${NC}"
echo -e "${DIM}To fully remove it: sudo rm -rf ${SCRIPT_DIR}${NC}"
