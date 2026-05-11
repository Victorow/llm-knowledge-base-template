from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class UiSmokeTests(unittest.TestCase):
    def test_control_panel_window_constructs_offscreen(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets

        from kb_app.ui.app import ControlPanelWindow, PAGE_REGISTRY

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "kb"
            (root / "kb" / "daily").mkdir(parents=True)
            (root / "kb" / "knowledge").mkdir(parents=True)
            window = ControlPanelWindow(root, Path(tmp) / "app.db")

            self.assertEqual(window.stack.count(), len(PAGE_REGISTRY))
            self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
