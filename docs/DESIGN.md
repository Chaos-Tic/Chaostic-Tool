# Desktop design system

The UI preserves ChaosticTool's red identity in a quiet dark workspace. All
reusable visual styles live in `desktop/theme.py`.

| Token | Value | Use |
| --- | --- | --- |
| background | #0c1017 | Main workspace |
| sidebar | #10151e | Navigation |
| surface | #141b26 | Cards and alternating rows |
| border | #293344 | Component boundaries |
| text | #f0f3f9 | Primary content |
| muted | #a4afc2 | Secondary content |
| red | #ff4d64 | Brand and running state |
| green | #73deb0 | Ready and success, always paired with text |

Navigation, buttons, fields and tables have keyboard focus states. The desktop
uses system text controls, selectable logs and table selection. Labels are plain
text, including user-provided target names and tool output. No HTML interpretation
or terminal escape execution is used. Font: Segoe UI, 10 pt body, 29 px page title.
Spacing: 8, 12, 16, 20, 24, 30 px. Components include default, hover, pressed,
focused, disabled, empty, running and error states. Do not claim detection means
an external tool has been tested. Do not display mock metrics as real activity.
