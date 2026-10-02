# Desktop design system — Red Ops 1.1

The Desktop editions share the Linux CLI's red, charcoal and technical typography.
New profiles start dark; existing saved theme preferences remain unchanged.
`desktop/theme.py` is the source of truth for both palettes.

| Token | Light | Dark |
|---|---|---|
| Background | `#f1eeee` | `#090b10` |
| Surface | `#ffffff` | `#11141c` |
| Text | `#21171b` | `#edf0f5` |
| Muted text | `#65575d` | `#abb1c0` |
| Accent | `#c72c41` | `#ff4a55` |
| Primary button | `#ae2035` | `#c52b3b` |
| Success | `#147d40` | `#5fdda0` |

Use the bundled Orbitron for the brand title, Share Tech Mono for technical
metadata, and platform body/console fonts with fallbacks. Keep long descriptions
in the body font. The shared SVG monogram supplies the sidebar, home emblem and
packaged app icon; regenerate PNG/ICO using `python scripts/make-icon.py`.

Panels use fine borders, small corner radii and red alignment marks. Reserve solid
red for primary actions and selected navigation. Status colors also have text
labels. Main text and primary button colors meet a 4.5:1 contrast ratio in tests.
Keep keyboard focus visible and execution output selectable.

The active target precedes counters and shortcuts. At compact widths the decorative
emblem disappears and the home page scrolls; it must not force a wider window.
The hero has no idle animation or simulated telemetry. Counters reflect saved
operations and detected tools. Optional interaction effects can be disabled.

English is the default language; French is selectable in Settings. Ctrl+K opens
search and F6 opens Execution. Theme changes retain the active target and saved
data. `tests/test_redops.py` covers contrast, theme persistence and compact layout.

`scripts/capture-screens.py` renders a temporary demo profile and runs a real local
diagnostic. Its screenshots contain no user history and are captured with Qt's
offscreen renderer on the named OS, not a native compositor session.
The [NEXUS notes](NEXUS.md) and [Operation Deck notes](NEXUS_VISUALS.md) are historical.
