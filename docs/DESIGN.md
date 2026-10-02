# Desktop design system

The current Desktop interface uses an orange accent, a light default theme and
a persistent dark theme. `desktop/theme.py` is the source of truth.

| Token | Light | Dark |
|---|---|---|
| Background | `#edf0f4` | `#0f1216` |
| Surface | `#ffffff` | `#171b21` |
| Text | `#12141a` | `#e7eaf0` |
| Muted text | `#5b6472` | `#98a1af` |
| Accent | `#ea580c` | `#f97316` |
| Success | `#16a34a` | `#34d399` |

Use standard Qt controls, readable logs, visible keyboard focus and text labels
alongside status colors. Segoe UI and Consolas are requested with platform font
fallbacks. English is the default language; French is selectable in Settings.
Ctrl+K opens search and F6 opens Execution.

Animations can be disabled. Ambient refresh settings are targets, not GPU frame
rate guarantees. Counts and execution indicators must reflect actual state.
The [NEXUS notes](NEXUS.md) and [Operation Deck notes](NEXUS_VISUALS.md) are
historical design explorations, not the current visual specification.
