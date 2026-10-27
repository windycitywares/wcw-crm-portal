"""Test mode only applies while the copy is on the same migration as the live data (no database needed)."""

import unittest

from app.core.appmode import LIVE, TEST, ModeState


class CopyCurrentTests(unittest.TestCase):
    def test_behind_copy_falls_back_to_live(self):
        self.assertEqual(ModeState(chosen=TEST, test_exists=True).effective, TEST)
        self.assertEqual(ModeState(chosen=TEST, test_exists=True, test_current=False).effective, LIVE)
        self.assertEqual(ModeState(chosen=TEST, test_exists=False).effective, LIVE)
        self.assertEqual(ModeState(chosen=LIVE, test_exists=True, test_current=False).effective, LIVE)


if __name__ == "__main__":
    unittest.main()
