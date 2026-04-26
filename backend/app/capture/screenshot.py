import os
from typing import Optional

import mss
import numpy as np
from PIL import ImageGrab


def _pil_bgr_from_bbox(bbox: Optional[tuple[int, int, int, int]] = None) -> np.ndarray:
    """
    Windows path: exclude layered windows so transparent overlays don't pollute OCR.
    ImageGrab returns RGB; convert to BGR for OpenCV consumers.
    """
    image = ImageGrab.grab(
        bbox=bbox,
        include_layered_windows=False,
        all_screens=False,
    )
    rgb = np.array(image)
    return rgb[:, :, ::-1].copy()


def _mss_region(region: dict) -> np.ndarray:
    with mss.mss() as sct:
        monitor = {
            "top": region["y"],
            "left": region["x"],
            "width": region["w"],
            "height": region["h"],
        }
        raw = sct.grab(monitor)
        img = np.frombuffer(raw.bgra, dtype=np.uint8).reshape(raw.height, raw.width, 4)
        return img[:, :, :3].copy()


def _mss_full() -> np.ndarray:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)
        img = np.frombuffer(raw.bgra, dtype=np.uint8).reshape(raw.height, raw.width, 4)
        return img[:, :, :3].copy()


def capture_region(region: dict) -> np.ndarray:
    """Capture a screen region and return as BGR numpy array."""
    if os.name == "nt":
        try:
            x = int(region["x"])
            y = int(region["y"])
            w = int(region["w"])
            h = int(region["h"])
            return _pil_bgr_from_bbox((x, y, x + w, y + h))
        except Exception:
            pass
    return _mss_region(region)


def capture_full() -> np.ndarray:
    """Capture the primary monitor and return as BGR numpy array."""
    if os.name == "nt":
        try:
            return _pil_bgr_from_bbox()
        except Exception:
            pass
    return _mss_full()


def get_screen_size() -> tuple[int, int]:
    """Return (width, height) of the primary monitor."""
    with mss.mss() as sct:
        m = sct.monitors[1]
        return m["width"], m["height"]
