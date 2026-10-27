# Media

Every visual asset here is synthetic or rendered from deterministic fixtures: no
real target, confidential engagement data, customer domain or live network trace is ever shown.

| File | Made by |
| --- | --- |
| `banner.svg`, `banner-dark.svg` | Hand-crafted SVG with frosted-glass gradients (`<picture>` header) |
| `demo.gif` | `scripts/render-docs.sh` (cross-faded demo loop via ImageMagick & ffmpeg, 20 fps, bayer dither <= 2 MB) |
| `liquid-glass-accueil.png`, `liquid-glass-arsenal.png`, `liquid-glass-flows.png`, `liquid-glass-execution.png`, `liquid-glass-historique.png`, `liquid-glass-dark.png`, `liquid-glass-compact.png` | `scripts/render-docs.sh` (`scripts/capture-screens.py` offscreen with synthetic targets) |

Regenerate after a visual or theme change:
```bash
scripts/render-docs.sh
```

## Aligned banner and hero

`banner(-dark).png` and `hero(-dark).{png,gif}` come from the shared Chaos-Tic template (same grid, background and glass frame for all three tools), built from the captures in this folder. ChaosticTool is a security tool, so the dark variant is the default.
