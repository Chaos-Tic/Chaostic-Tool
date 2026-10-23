# GitHub updates

Desktop 1.3 and CLI 1.5 use the public `Chaos-Tic/Chaostic-Tool` releases. A single
latest-release request contains separate Desktop and CLI versions; an edition
never treats the other edition's tag as its own update. Drafts and prereleases are
excluded. No update is inferred from commits or an unmerged branch.

Automatic checks run in the background at most once per day, including after a
network failure. Manual checks request fresh metadata. Switch automatic checks
off in Settings → About, or in the CLI's **u → Application updates** menu. The CLI
also accepts `--no-update-check` and `CHAOSTIC_UPDATE_CHECK=0`.

The request is anonymous: no account identifier, token, target, settings, scan
result or command output is sent. GitHub sees the IP address of the request.
The cache and preference remain in the local user data directory.

## Applying a proposed update

- **Linux package:** the application identifies its installed package and proposes
  the existing apt, dnf/zypper or AUR update commands. The user confirms them;
  system authentication happens in a terminal. Restart the application afterwards.
  A repository may need time to synchronize after a GitHub release.
- **Windows:** after confirmation, download the matching x64/ARM64 installer,
  verify its SHA-256 and open it. Follow the installer prompts. Normal Windows
  downloaded-file security checks remain enabled.
- **macOS:** download and verify the matching DMG after confirmation, then open it.
  Complete the normal macOS application replacement.
- **AppImage:** download and verify the matching architecture. A second confirmation
  replaces the current user-owned AppImage atomically and keeps a `.previous-*`
  backup. Close and restart the application; restore the backup manually if needed.
- **Portable archive:** download and verify the new archive, then use its normal
  installation instructions. The updater does not guess which arbitrary folder
  should be overwritten.
- **Source checkout:** open the release instructions. Uncommitted work is preserved.

An operation must finish before a Desktop update starts. A mismatched checksum or
cancelled download is discarded and is never launched. Personal targets, settings
and results are separate from the application and remain in place.

Downloaded files stay under the application's user data `updates` folder. SHA-256
checks file integrity against the published release; it is not a publisher signature.
