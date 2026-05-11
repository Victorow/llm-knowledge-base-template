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
        show_action  = menu.addAction("Abrir Painel")
        menu.addSeparator()
        quit_action  = menu.addAction("Fechar Aplicação")

        show_action.triggered.connect(self._show_window)
        quit_action.triggered.connect(self.app.quit)

        self.tray = QtWidgets.QSystemTrayIcon()
        self.tray.setToolTip("LLM Knowledge Base — rodando em segundo plano")

        icon = self._load_icon()
        if icon is not None:
            self.tray.setIcon(icon)
            # Also set on the Qt application so the taskbar gets the icon
            self.app.setWindowIcon(icon)

        self.tray.setContextMenu(menu)
        # Single-click or double-click to open
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

        # Override the window close button to hide instead of quit
        self.window.window.closeEvent = self._on_close_event

        return True

    def _show_window(self) -> None:
        self.window.window.showNormal()
        self.window.window.raise_()
        self.window.window.activateWindow()

    def _on_activated(self, reason) -> None:
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            if reason in (
                QSystemTrayIcon.ActivationReason.Trigger,
                QSystemTrayIcon.ActivationReason.DoubleClick,
            ):
                self._show_window()
        except Exception:
            self._show_window()

    def _on_close_event(self, event) -> None:
        """Hide to tray instead of closing when user presses X."""
        event.ignore()
        self.window.window.hide()
        if self.tray:
            self.tray.showMessage(
                "LLM Knowledge Base",
                "App continua em segundo plano. Clique aqui para abrir.",
                self.tray.icon(),
                3000,
            )

    @staticmethod
    def _load_icon():
        try:
            from kb_app.ui.resources.qicon import app_icon
            return app_icon()
        except Exception:
            return None
