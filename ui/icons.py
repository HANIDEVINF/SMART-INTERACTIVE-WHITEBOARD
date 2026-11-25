"""Vector icon set rendered from inline SVG (no image files to ship or lose).

Icons use a 24x24 grid with a 1.8 px round stroke. They are rasterised at 2x for crisp edges
on high-DPI screens and cached per (name, colour, size).
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{c}" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')

_BODIES = {
    "home": '<path d="M3.5 11 12 3.5 20.5 11"/><path d="M5.5 9.5V20h4.5v-5.5h4V20h4.5V9.5"/>',
    "pen": '<path d="M4 20l1-4.5L16.5 4a2.1 2.1 0 013 3L8 18.5 4 20z"/><path d="M14.5 6l3 3"/>',
    "eraser": '<path d="M8.5 20H20"/><path d="M5 15.5 14.5 6a2 2 0 012.8 0l2.7 2.7a2 2 0 010 2.8L11.5 20H8L5 17a1.6 1.6 0 010-1.5z"/><path d="M10 10.5l5 5"/>',
    "line": '<path d="M5 19 19 5"/><circle cx="5" cy="19" r="1.6"/><circle cx="19" cy="5" r="1.6"/>',
    "rect": '<rect x="4" y="6" width="16" height="12" rx="2.5"/>',
    "circle": '<circle cx="12" cy="12" r="8"/>',
    "text": '<path d="M5.5 6.5V5h13v1.5M12 5v14M9 19h6"/>',
    "undo": '<path d="M9 7 4.5 11.5 9 16"/><path d="M4.5 11.5h9a4.5 4.5 0 010 9H10"/>',
    "redo": '<path d="M15 7l4.5 4.5L15 16"/><path d="M19.5 11.5h-9a4.5 4.5 0 000 9H14"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l.8 12.5h9.4L17.5 7M10 11v5.5M14 11v5.5"/>',
    "save": '<path d="M5 4h11l4 4v12H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
    "folder": '<path d="M3.5 7.5h6l2 2h9v10h-17z"/>',
    "image": '<rect x="3.5" y="5" width="17" height="14" rx="2"/><circle cx="8.5" cy="10" r="1.5"/><path d="M3.5 17l5.5-5 4 4 3-2.5 4.5 4"/>',
    "fullscreen": '<path d="M4.5 9.5v-5h5M14.5 4.5h5v5M19.5 14.5v5h-5M9.5 19.5h-5v-5"/>',
    "exitfs": '<path d="M9.5 4.5v5h-5M14.5 4.5v5h5M19.5 14.5h-5v5M4.5 14.5h5v5"/>',
    "teaching": '<path d="M3.5 5.5h6.5a2 2 0 012 2V20a2 2 0 00-2-2H3.5z"/><path d="M20.5 5.5H14a2 2 0 00-2 2V20a2 2 0 012-2h6.5z"/>',
    "calibrate": '<path d="M4.5 8.5v-4h4M15.5 4.5h4v4M19.5 15.5v4h-4M8.5 19.5h-4v-4"/><circle cx="12" cy="12" r="2.2"/><path d="M12 7.5v2M12 14.5v2M7.5 12h2M14.5 12h2"/>',
    "camera": '<path d="M3.5 8.5A1.5 1.5 0 015 7h2.5L9 4.5h6L16.5 7H19a1.5 1.5 0 011.5 1.5v9A1.5 1.5 0 0119 19H5a1.5 1.5 0 01-1.5-1.5z"/><circle cx="12" cy="13" r="3.5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.5M12 18v2.5M3.5 12H6M18 12h2.5M6 6l1.8 1.8M16.2 16.2 18 18M18 6l-1.8 1.8M7.8 16.2 6 18"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "pointer": '<path d="M5 3.5l13 7-5.5 1.8-2 5.7z"/>',
    "menu": '<path d="M4.5 7h15M4.5 12h15M4.5 17h15"/>',
    "keyboard": '<rect x="3" y="6.5" width="18" height="11" rx="2"/><path d="M7 10.5h.01M10.5 10.5h.01M14 10.5h.01M17 10.5h.01M7.5 14h9"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "arrow-left": '<path d="M19 12H5M11 6l-6 6 6 6"/>',
}


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#FFFFFF", size: int = 22) -> QPixmap:
    scale = 2
    renderer = QSvgRenderer(QByteArray(_SVG.format(c=color, body=_BODIES[name]).encode("utf-8")))
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
    painter.end()
    pm.setDevicePixelRatio(scale)
    return pm


def icon(name: str, color: str = "#FFFFFF", size: int = 22, on_color: str | None = None) -> QIcon:
    """QIcon for `name`. When `on_color` is given it is used for the checked state."""
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(pixmap(name, on_color or color, size), QIcon.Mode.Normal, QIcon.State.On)
    ic.addPixmap(pixmap(name, "#B7B9CC", size), QIcon.Mode.Disabled, QIcon.State.Off)
    return ic


def available_icons() -> list[str]:
    return sorted(_BODIES)
