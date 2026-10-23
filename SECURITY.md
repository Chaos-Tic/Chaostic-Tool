# Update privacy and verification

ChaosticTool checks only public releases of `Chaos-Tic/Chaostic-Tool`. Automatic
checks make at most one anonymous HTTPS request per day to GitHub's latest-release
API. No target, command output, account identifier, cookie or token is included.
GitHub can see the request IP address. Manual checks request fresh metadata.

Disable automatic checks in Application updates, with `--no-update-check`, or
with `CHAOSTIC_UPDATE_CHECK=0`. The preference and daily cache stay in the user
data directory. Failed checks never prevent startup and do not run an installer.

Installed Linux packages update through their existing apt, dnf/zypper or AUR
channel, only after the user confirms the displayed commands. Source checkouts are
never reset or overwritten by the updater. Package removal preserves user results.

The shared desktop downloader requires the exact release artifact's SHA-256 file,
rejects malformed or mismatched hashes and discards incomplete downloads. Checksums
protect file integrity; they do not replace an operating-system publisher signature.
