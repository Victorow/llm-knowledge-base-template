"""Load the app QIcon from the embedded PNG data."""
from __future__ import annotations

import base64


def app_icon():
    """Return a QIcon for the app, or None if Qt is not available."""
    try:
        from PySide6 import QtGui
        from kb_app.ui.resources.icon_data import ICON_PNG_B64
    except ImportError:
        return None

    raw = base64.b64decode(ICON_PNG_B64)
    pixmap = QtGui.QPixmap()
    pixmap.loadFromData(raw, "PNG")
    return QtGui.QIcon(pixmap)
