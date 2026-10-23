# Desktop design system — Liquid Glass development preview

This visual refresh follows the peach, sky and lilac material family of Lorenz
and Lyapunov. It is a source development preview, not part of Desktop 1.1.5.

## Surfaces and typography

The central widget paints three soft color fields behind the sidebar and working
area. Cards combine a tinted translucent body, diffuse shadow, bright outer rim
and inner reflection. These layers are rendered by Qt and work without compositor
blur. Settings → Appearance → Reduce transparency replaces glass bodies with
opaque surfaces and removes background color fields and surface reflections.

Use installed Geist, Segoe UI Variable, Segoe UI, Inter, Cantarell or Noto Sans,
with the platform font as fallback. Technical commands and addresses retain a
monospace face. Page titles and navigation use sans-serif text.

`desktop/theme.py` owns control colors, fonts and preferences;
`desktop/identity.py` owns panel painting, branding and numbered navigation;
`desktop/hud.py` owns the environment, welcome card and shared motion clock.

| Token | Light | Dark |
|---|---|---|
| Background | `#f4f1fa` | `#191d30` |
| Surface | `#ffffff` | `#252b42` |
| Text | `#151820` | `#f3f4f8` |
| Muted text | `#4a5060` | `#c0c7d9` |
| Accent | `#385cad` | `#a8dafa` |
| Primary button | `#364d87` | `#425c9c` |

The tested text token pairs and white primary-button text meet a 4.5:1 contrast
threshold. Status colors retain text labels. Navigation has a persistent selection
marker, a heavier active label and a visible keyboard focus ring.

## Layout and preferences

The home screen contains the welcome actions, active target, local counts, shortcuts
and recent operations. Decorative lenses carry no status information. At 900 × 600,
secondary welcome text and lenses disappear, the wordmark shrinks, and content
remains vertically scrollable without horizontal scrolling. English and French are
supported. Ctrl+K opens search; F6 opens Execution.

New profiles start light. Saved dark/light preferences are preserved. Reduced
transparency survives theme changes and application restarts. Existing animation
controls continue to disable interaction transitions; the home has no idle motion.
No target or execution behavior changes as part of the visual refresh.

## Assets and verification

The SVG icon preserves the circle/lightning motif in the shared pastel palette.
The sidebar and window use this same vector. `scripts/make-icon.py` generates PNG
and multi-size Windows ICO assets from it, including 16 px. macOS ICNS is generated
on macOS by the same script; native packaging needs platform verification.

`tests/test_redops.py` checks contrast, saved themes, reduced transparency,
compact layout and French keyboard navigation. The historical test filename remains
for compatibility. `tests/test_visual_motion.py` checks actions and animation cleanup.

`scripts/render-docs.sh` regenerates icons and the light-first documentation
screenshots. `scripts/capture-screens.py` uses isolated sample targets, history and
synthetic execution text; it starts no operation or network request. Tool availability
is detected on the rendering machine and is not a compatibility certification.
Set `CHAOSTIC_CAPTURE_LANGUAGE=fr` for French or `QT_SCALE_FACTOR=1.5` for scale review.
Offscreen Linux captures do not certify native compositor or Windows/macOS behavior.

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
