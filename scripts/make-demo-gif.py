#!/usr/bin/env python3
"""Builds a lightweight, high-quality demo.gif (<= 2.5 MB) showing ChaosticTool's reconnaissance pipeline.

Uses ImageMagick and ffmpeg at 20 fps with a 96-color bayer dither palette
(Lyapunov / Lorenz standard).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "docs/media"

SLIDES = [
    ("liquid-glass-accueil.png", 35),     # 1.75s Home / Target selector
    ("liquid-glass-arsenal.png", 35),     # 1.75s 32 Offensive profiles
    ("liquid-glass-flows.png", 35),       # 1.75s Orchestrated reconnaissance flow
    ("liquid-glass-execution.png", 45),   # 2.25s Live PTY terminal output
    ("liquid-glass-historique.png", 40),  # 2.0s Results & mission report
]

# Dark counterpart: identical cadence/transitions, dark-themed captures.
SLIDES_DARK = [(name.replace(".png", "-dark.png"), hold) for name, hold in SLIDES]


def generate_gif(out_path: Path, slides=SLIDES):
    if not shutil.which("ffmpeg") or not shutil.which("magick"):
        print("ffmpeg or magick not found; skipping gif build", file=sys.stderr)
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        frame_idx = 0

        # Pre-resize all slide images to 800x506 for crisp display & compact size
        resized_slides = []
        for name, _ in slides:
            src = MEDIA / name
            if not src.exists():
                print(f"Source image {src} missing", file=sys.stderr)
                return False
            dst = tmp / f"resized_{name}"
            subprocess.run(
                ["magick", str(src), "-resize", "800x506!", str(dst)],
                check=True,
            )
            resized_slides.append(dst)

        n_slides = len(slides)
        transition_frames = 6

        for i, (name, hold_frames) in enumerate(slides):
            current_img = resized_slides[i]
            next_img = resized_slides[(i + 1) % n_slides]

            # Hold frames
            for _ in range(hold_frames):
                frame_idx += 1
                dst_frame = tmp / f"frame_{frame_idx:04d}.png"
                shutil.copyfile(current_img, dst_frame)

            # Cross-fade transition frames to next slide
            for step in range(1, transition_frames + 1):
                alpha = int((step / (transition_frames + 1)) * 100)
                frame_idx += 1
                dst_frame = tmp / f"frame_{frame_idx:04d}.png"
                subprocess.run(
                    [
                        "magick",
                        "composite",
                        "-blend",
                        f"{alpha}%",
                        str(next_img),
                        str(current_img),
                        str(dst_frame),
                    ],
                    check=True,
                )

        # Encode via ffmpeg with differential palette bayer dither
        vf_filter = (
            "fps=20,split[s0][s1];"
            "[s0]palettegen=max_colors=96:stats_mode=diff[p];"
            "[s1][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle"
        )
        subprocess.run(
            [
                "ffmpeg",
                "-loglevel",
                "error",
                "-y",
                "-framerate",
                "20",
                "-i",
                str(tmp / "frame_%04d.png"),
                "-vf",
                vf_filter,
                "-loop",
                "0",
                str(out_path),
            ],
            check=True,
        )

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"Generated {out_path} ({size_mb:.2f} MB)")
    return True


if __name__ == "__main__":
    generate_gif(MEDIA / "demo.gif", SLIDES)
    generate_gif(MEDIA / "demo-dark.gif", SLIDES_DARK)
