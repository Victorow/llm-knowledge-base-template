from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kb_app.profiles.store import ProfileStore


class ProfileStoreTests(unittest.TestCase):
    def make_store(self) -> tuple[tempfile.TemporaryDirectory[str], ProfileStore]:
        temp = tempfile.TemporaryDirectory()
        store = ProfileStore(Path(temp.name) / "app.db")
        return temp, store

    def test_creates_profiles_and_selects_active_profile(self) -> None:
        temp, store = self.make_store()
        with temp:
            first = store.create_profile("Personal", "D:/kb/personal", backend="codex")
            second = store.create_profile("Work", "D:/kb/work", backend="claude")

            store.set_active_profile(second)
            active = store.get_active_profile()

            self.assertIsNotNone(active)
            self.assertEqual(active.id, second)
            self.assertEqual(active.name, "Work")
            self.assertEqual(active.backend, "claude")
            self.assertFalse(store.get_profile(first).active)

    def test_settings_round_trip_json_values(self) -> None:
        temp, store = self.make_store()
        with temp:
            store.set_setting("daily_compile_enabled", True)
            store.set_setting("daily_compile_time", "17:00")

            self.assertIs(store.get_setting("daily_compile_enabled"), True)
            self.assertEqual(store.get_setting("daily_compile_time"), "17:00")
            self.assertEqual(store.get_setting("missing", "fallback"), "fallback")


if __name__ == "__main__":
    unittest.main()
