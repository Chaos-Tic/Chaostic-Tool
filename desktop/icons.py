from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "overview": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "target": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/>',
    "tools": '<path d="M4 7h16v13H4zM8 7V4h8v3M4 12h16M10 11v3h4v-3"/>',
    "run": '<path d="M7 4l13 8-13 8z"/>',
    "history": '<path d="M4 8a9 9 0 1 1-1 7M4 3v5H0M12 7v5l4 3"/>',
    "settings": '<path d="M3 6h18M3 12h18M3 18h18"/><circle cx="8" cy="6" r="2" fill="#10151e"/><circle cx="16" cy="12" r="2" fill="#10151e"/><circle cx="10" cy="18" r="2" fill="#10151e"/>',
}


def icon(name):
    data = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="#a4afc2" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
    renderer = QSvgRenderer(QByteArray(data.encode()))
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
