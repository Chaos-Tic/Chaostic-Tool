# User Guide

[Back to the README](../README.md)

ChaosticTool is designed for security auditors, penetration testers, and red teams.
It structures complex security reconnaissance into manageable, repeatable phases
accessible either through your shell or a frosted-glass desktop application.

## 1. Command-Line Interface (CLI / TUI)

The CLI binary is named `chaostictool`. It requires no X11 or Wayland server and runs
natively in any terminal emulator.

### Runtime and update checks
```bash
chaostictool --check-installation
chaostictool --check-updates
```

Profile selection and execution currently happen inside the interactive TUI. A
machine-readable catalog and non-interactive profile runner are planned, but are not
part of the current command-line contract.

### Interactive TUI Fullscreen Mode
If launched without arguments in an interactive terminal, `chaostictool` opens a
full-screen Rich TUI navigator with keyboard shortcuts:
- `Tab` / `Shift+Tab`: Switch between targets, categories, and profiles
- `Enter`: Select or launch profile
- `Esc` or `q`: Quit or return to the main dashboard

---

## 2. Liquid Glass Desktop (GUI)

Launch the desktop interface via:
```bash
chaostictool-desktop
```

### Key Areas:
1. **Target Selector**: Set the active engagement scope (Domain, IP, CIDR block, or URL). Targets are validated immediately and saved to your private local history.
2. **Arsenal**: Filter tools and launch presets by phase or keyword. Each card displays requirements and executable status.
3. **Flow Designer**: Chain multiple scans sequentially. For example:
   *Phase 1: Subfinder* ➔ *Phase 2: httpx probe* ➔ *Phase 3: Katana crawl*
4. **Interactive PTY Terminal**: Real-time terminal with ANSI color support, scrollback buffer, text selection, and instantaneous interruption controls (`Stop` button / `Ctrl+C`).
5. **History & Anonymization**: Review past executions, export clean JSON reports, or delete run history with atomic link-traversal protection.

---

## 3. Themes and Motion Settings

ChaosticTool supports two handcrafted visual modes:
- **Light Pastel**: Translucent frosted-glass panels with soft sky-blue, violet, and coral reflections.
- **Dark Neon**: Midnight canvas (`#0b0f19`) with cyan, purple, and amber accents.

To adjust animations or force static rendering (useful over low-bandwidth remote X11/SSH sessions):
- Toggle **Reduced Motion** in settings or run with `CHAOSTIC_REDUCED_MOTION=1`.

---

## 4. API Keys

A few bundled tools gain extra capability when you provide an API key: Shodan
(host lookups, the nmap `shodan-api` script and the passive source), WPScan (the
WordPress vulnerability database), and a GitHub token (higher API rate limits
for the OSINT sources such as amass, subfinder and gau).

Set them once and they persist across launches:
- **Desktop**: *Settings ➔ API keys*.
- **Terminal**: main menu entry **`k` · API keys**.

Keys are stored in the operating system's **secure key store** — Windows
Credential Manager, macOS Keychain, or the Linux Secret Service — so they are
encrypted at rest and never written to disk in clear text. When no secure store
is available (for example a headless root shell with no Secret Service), keys
are kept only for the current session; export the variable in your shell to
persist them there.

Each stored key is passed to the relevant tool through the environment variable
it reads (`SHODAN_API_KEY`, `WPSCAN_API_TOKEN`, `GITHUB_TOKEN`). A value already
present in your shell environment always takes precedence over the stored one.

---

## 5. Subdomain Scope

When the target is a **domain**, you can have host-targeted tools run against the
domain *and* all of its subdomains.

- **Discovery**: enumerate the subdomains once with subfinder (recommended) or
  amass. subfinder is the primary source; amass is used as a best-effort
  complement and is allowed to return nothing without failing. Results are
  validated to stay within the domain and cached per target, so they are reused
  across launches.
- **Desktop**: on the *Targets* page, use **Enumerate subdomains**, then tick
  **Include subdomains in scans**.
- **Terminal**: in **Configure target**, choose `e` to enumerate (and `t` to
  toggle the scope).

With the scope on, launching a host-targeted profile (for example an nmap or
Shodan lookup) runs it sequentially against the base host first, then each
subdomain, each with its own saved results. Profiles that do not target a host
run once as usual.
