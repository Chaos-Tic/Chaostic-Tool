from PySide6.QtCore import QByteArray, Qt, QRectF
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "overview": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "target": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/>',
    "tools": '<path d="M4 7h16v13H4zM8 7V4h8v3M4 12h16M10 11v3h4v-3"/>',
    "run": '<path d="M7 4l13 8-13 8z"/>',
    "history": '<path d="M4 8a9 9 0 1 1-1 7M4 3v5H0M12 7v5l4 3"/>',
    "settings": '<path d="M3 6h18M3 12h18M3 18h18"/><circle cx="8" cy="6" r="2" fill="#10151e"/><circle cx="16" cy="12" r="2" fill="#10151e"/><circle cx="10" cy="18" r="2" fill="#10151e"/>',
    "flow": '<circle cx="5" cy="12" r="2.4"/><circle cx="18" cy="5" r="2.4"/><circle cx="18" cy="19" r="2.4"/><path d="M7 11l9-5M7 13l9 5"/>',
}


def icon(name, color="#a4afc2"):
    data = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
    renderer = QSvgRenderer(QByteArray(data.encode()))
    pixmap = QPixmap(64, 64)
    pixmap.setDevicePixelRatio(2.0)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, 32, 32))
    painter.end()
    return QIcon(pixmap)
