import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import auto_screenshot  # noqa: E402


class AutoScreenshotTests(unittest.TestCase):
    def test_frame_hash_matches_identical_frames(self) -> None:
        frame = np.zeros((120, 200, 3), dtype=np.uint8)
        frame[:, :] = (10, 20, 30)

        self.assertEqual(auto_screenshot._frame_hash(frame), auto_screenshot._frame_hash(frame.copy()))

    def test_frame_hash_changes_when_frame_changes(self) -> None:
        left = np.zeros((120, 200, 3), dtype=np.uint8)
        right = np.zeros((120, 200, 3), dtype=np.uint8)
        right[20:80, 40:140] = (255, 255, 255)

        self.assertNotEqual(auto_screenshot._frame_hash(left), auto_screenshot._frame_hash(right))

    def test_interval_is_clamped(self) -> None:
        self.assertEqual(auto_screenshot._normalize_interval(1), 2)
        self.assertEqual(auto_screenshot._normalize_interval(999), 300)
        self.assertEqual(auto_screenshot._normalize_interval("12"), 12)


if __name__ == "__main__":
    unittest.main()
