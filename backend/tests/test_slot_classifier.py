import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.capture import slot_classifier  # noqa: E402


class SlotClassifierTests(unittest.TestCase):
    def _write_sample(self, path: Path, bgr: tuple[int, int, int]) -> None:
        img = np.zeros((96, 96, 3), dtype=np.uint8)
        img[:] = np.array(bgr, dtype=np.uint8)
        cv2.circle(img, (48, 36), 18, (255, 255, 255), -1)
        cv2.rectangle(img, (18, 56), (78, 88), tuple(max(0, c - 40) for c in bgr), -1)
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), img)

    def test_build_and_match_grouped_slot_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            samples = root / "samples"
            model_path = root / "slot_model.json"

            self._write_sample(samples / "board" / "alpha" / "a1.png", (20, 40, 220))
            self._write_sample(samples / "board" / "alpha" / "a2.png", (30, 60, 210))
            self._write_sample(samples / "board" / "beta" / "b1.png", (220, 80, 30))
            self._write_sample(samples / "bench" / "alpha" / "a1.png", (30, 50, 210))
            self._write_sample(samples / "bench" / "gamma" / "g1.png", (50, 210, 70))

            model = slot_classifier.build_slot_model(samples, model_path)

            self.assertEqual(sorted(model.keys()), ["bench", "board"])
            self.assertTrue(model_path.exists())

            with open(model_path, "r", encoding="utf-8") as f:
                persisted = json.load(f)
            self.assertIn("board", persisted)
            self.assertIn("bench", persisted)

            slot_classifier.reload()
            original_path = slot_classifier._MODEL_PATH
            try:
                slot_classifier._MODEL_PATH = str(model_path)
                slot_classifier.reload()

                query = cv2.imread(str(samples / "board" / "alpha" / "a1.png"))
                name, conf = slot_classifier.match_slot_unit(query, group="board", min_conf=0.50)
                self.assertEqual(name, "alpha")
                self.assertGreater(conf, 0.90)

                self.assertTrue(slot_classifier.slot_model_available("board"))
                self.assertTrue(slot_classifier.slot_model_available("bench"))
            finally:
                slot_classifier._MODEL_PATH = original_path
                slot_classifier.reload()

    def test_empty_label_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            samples = root / "samples"
            model_path = root / "slot_model.json"

            self._write_sample(samples / "board" / "alpha" / "a1.png", (40, 80, 220))

            empty = np.zeros((96, 96, 3), dtype=np.uint8)
            empty[:] = (30, 30, 35)
            cv2.imwrite(str(samples / "board" / "__empty__" / "e1.png"), empty)

            slot_classifier.build_slot_model(samples, model_path)

            slot_classifier.reload()
            original_path = slot_classifier._MODEL_PATH
            try:
                slot_classifier._MODEL_PATH = str(model_path)
                slot_classifier.reload()

                name, score = slot_classifier.match_slot_unit(empty, group="board", min_conf=0.50)
                self.assertIsNone(name)
                self.assertLess(score, 0.08)
            finally:
                slot_classifier._MODEL_PATH = original_path
                slot_classifier.reload()


if __name__ == "__main__":
    unittest.main()
