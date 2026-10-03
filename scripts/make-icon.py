"""Build platform icons from the original CLI/Red Ops mascot, without redrawing it."""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage


app = QGuiApplication.instance() or QGuiApplication(sys.argv)
assets = Path(__file__).resolve().parent.parent / "desktop/assets"
sys.path.insert(0, str(assets.parent.parent))
from desktop.branding import MASCOT_RECT
artwork = QImage(str(assets / "red-ops-banner.png"))
if artwork.isNull():
    raise RuntimeError("Original Red Ops artwork is missing")
mascot = artwork.copy(*MASCOT_RECT)


def render_icon(size):
    return mascot.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    image = render_icon(size)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    images.append((size, bytes(buffer.data())))
offset = 6 + 16 * len(images)
directory = bytearray(struct.pack("<HHH", 0, 1, len(images)))
content = bytearray()
for size, data in images:
    directory += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
    content += data
    offset += len(data)
(assets / "icon.ico").write_bytes(directory + content)

(assets / 'icon.png').write_bytes(images[-1][1])
if sys.platform == 'darwin':
    import subprocess
    iconset = assets / 'icon.iconset'
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            side = size * scale
            image = render_icon(side)
            suffix = '@2x' if scale == 2 else ''
            image.save(str(iconset / f'icon_{size}x{size}{suffix}.png'))
    subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(assets/'icon.icns')], check=True)
