from __future__ import annotations

import unittest


class UiImportTests(unittest.TestCase):
    def test_ui_modules_import_without_starting_event_loop(self) -> None:
        from kb_app.ui import app, tray

        self.assertTrue(app.PYSIDE_PACKAGE_NAME)
        self.assertTrue(hasattr(tray, "TrayController"))


if __name__ == "__main__":
    unittest.main()
