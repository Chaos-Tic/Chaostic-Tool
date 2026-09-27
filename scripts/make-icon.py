"""Render the repository-owned vector icon into the Windows icon container."""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

app = QGuiApplication.instance() or QGuiApplication(sys.argv)
assets = Path(__file__).resolve().parent.parent / "desktop/assets"
renderer = QSvgRenderer(str(assets / "icon.svg"))
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
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
