# Desktop design system — original Red Ops identity (1.1.1)

The source of the identity is the Linux CLI README, not a separate Desktop logo.
The unmodified repository-owned `assets/Banner.png` is shipped as
`desktop/assets/red-ops-banner.png`. The home panel displays the complete artwork;
sidebar source rectangles display its original mascot and wordmark on every page.
Keep this packaged copy byte-identical when the source banner changes.

## Visual language

- Deep black surfaces, distressed white/red wordmark and the hooded mascot.
- The slashed ring from the wordmark, simplified into the vector application icon.
- Numbered navigation with cut-corner selection and explicit keyboard focus.
- Double industrial frames, cut corners and restrained red alignment marks.
- Orbitron page titles, Share Tech Mono metadata/navigation and readable body text.
- Quiet data areas: no texture behind logs, table cells or input fields.

`desktop/identity.py` owns the original-artwork display, panel geometry and custom
navigation. `desktop/theme.py` owns the adaptive control palette. Brand artwork and
sidebar retain their black background in both themes; working surfaces adapt.

| Token | Light | Dark |
|---|---|---|
| Background | `#f1eeee` | `#080808` |
| Surface | `#ffffff` | `#101010` |
| Text | `#21171b` | `#f2eeee` |
| Muted text | `#65575d` | `#bdb3b3` |
| Accent | `#c72c41` | `#ff5454` |
| Primary button | `#ae2035` | `#b91624` |
| Success | `#147d40` | `#5fdda0` |

Text and primary button token pairs meet the tested 4.5:1 contrast threshold.
Status colors have text labels. Keep focus visible, buttons keyboard-operable and
execution output selectable. Do not use decorative artwork as live status data;
the home counters and execution status are populated from actual application state.

## Layout and behavior

The home action dock leads to the arsenal and flows. Active target and local
counters share an operation row, followed by shortcuts and recent results.
The original banner preserves its aspect ratio at smaller widths; secondary hero
copy disappears below 850 px. The sidebar mascot shrinks in windows shorter than
740 px. The interface remains usable at 900 × 600 in English and French.

English is the default language; French is selectable in Settings. Ctrl+K opens
search and F6 opens Execution. New profiles start dark. Existing saved theme
preferences, targets and results are preserved. No idle animation is introduced.

## Verification and assets

`tests/test_redops.py` checks palette contrast, saved themes, compact layout,
active-target persistence and French keyboard navigation. Packaged smoke tests
assert that the original artwork is available before running the local diagnostic.
`scripts/make-icon.py` regenerates PNG/ICO and macOS ICNS from `desktop/assets/icon.svg`.
Desktop 1.1.5 restores the red lightning/crosshair icon used in 1.1.2, following
the owner's visual preference. The application, Windows installer and shortcuts,
Linux launcher and macOS bundle use this vector icon. The original hooded mascot
and wordmark remain in the home screen and sidebar, sourced from `red-ops-banner.png`.
The Windows identity fix introduced in 1.1.4 is retained. Regenerate icons before
building; never overwrite an already published release to change its icon.

`scripts/capture-screens.py` uses a temporary demo profile and a real local
diagnostic. Screenshots use Qt offscreen rendering on the named OS. Set
`CHAOSTIC_CAPTURE_LANGUAGE=fr` for French and `QT_SCALE_FACTOR=1.5` for a 150% review.
These captures do not certify every native compositor, display or external tool.
The [NEXUS notes](NEXUS.md) and [Operation Deck notes](NEXUS_VISUALS.md) are historical.


## Windows taskbar identity

Before creating any Qt windows, the GUI sets the stable Windows AppUserModelID
`ChaosTic.ChaosticTool.Desktop`. Both installer shortcuts use the same ID and
explicitly point to the bundled `icon.ico`, rather than relying on Explorer's
cached executable association. The installer application ID (upgrade identity)
is unchanged. Background workers do not register a GUI identity.

Packaged Windows smoke tests read the real process AppUserModelID. CI also
installs the generated Windows package into a temporary directory and checks
the Start menu shortcut's AppUserModelID, target and icon resource, then uninstalls
it. An old already-running process must be closed normally and relaunched to
receive a new startup identity. Finish active operations before updating.

References: [Microsoft AppUserModelIDs](https://learn.microsoft.com/en-us/windows/win32/shell/appids)
and [Inno Setup shortcut properties](https://jrsoftware.org/ishelp/topic_iconssection.htm).
