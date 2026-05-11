"""System tray integration with graceful fallback."""

from __future__ import annotations


class TrayController:
    """Small wrapper around QSystemTrayIcon."""

    def __init__(self, app, window) -> None:
        self.app = app
        self.window = window
        self.tray = None

    def install(self) -> bool:
        try:
            from PySide6 import QtWidgets
        except ImportError:
            return False

        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return False

        menu = QtWidgets.QMenu()
        show_action = menu.addAction("Open Control Panel")
        quit_action = menu.addAction("Quit")
        show_action.triggered.connect(self.window.show)
        quit_action.triggered.connect(self.app.quit)

        self.tray = QtWidgets.QSystemTrayIcon()
        self.tray.setToolTip("LLM Knowledge Base")
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda _reason: self.window.show())
        self.tray.show()
        return True
