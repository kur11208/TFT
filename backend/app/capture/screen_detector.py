"""
Detect TFT screen state by sampling brightness patterns.

During selection screens (augment/forge/gods), a modal overlay appears over the
board, making the card zone significantly brighter than the board zone.
Regions are calculated as screen-size percentages to work at any resolution.
"""
import numpy as np
import cv2
from .screenshot import capture_region, get_screen_size

_OVERLAY_MIN = 28    # minimum card-zone brightness to even consider selection
_RATIO_MIN   = 1.10  # card-zone / board-zone brightness ratio


def _get_regions(sw: int, sh: int) -> tuple[dict, dict]:
    """Card zone (where augment/forge/god cards appear) and board zone."""
    card_zone = {
        "x": int(sw * 0.20),
        "y": int(sh * 0.14),
        "w": int(sw * 0.60),
        "h": int(sh * 0.42),
    }
    board = {
        "x": 0,
        "y": int(sh * 0.58),
        "w": int(sw * 0.50),
        "h": int(sh * 0.10),
    }
    return card_zone, board


def _brightness(region: dict) -> float:
    try:
        img = capture_region(region)
        return float(np.mean(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)))
    except Exception:
        return 0.0


def detect() -> str:
    """Return 'selection', 'normal', or 'unknown'."""
    try:
        sw, sh = get_screen_size()
        card_zone, board = _get_regions(sw, sh)
        c = _brightness(card_zone)
        b = _brightness(board)
        ratio = c / b if b > 0 else 0.0

        if c > _OVERLAY_MIN and b > 0 and ratio > _RATIO_MIN:
            return "selection"
        # Fallback: card zone is very bright (e.g. white card backgrounds)
        if c > 75 and b > 0 and c > b:
            return "selection"
        return "normal"
    except Exception:
        return "unknown"


def brightness_debug() -> dict:
    """Return raw brightness values for threshold calibration."""
    sw, sh = get_screen_size()
    card_zone, board = _get_regions(sw, sh)
    c = _brightness(card_zone)
    b = _brightness(board)
    ratio = c / b if b > 0 else 0.0
    is_sel = (c > _OVERLAY_MIN and b > 0 and ratio > _RATIO_MIN) or (c > 75 and b > 0 and c > b)
    return {
        "screen": f"{sw}x{sh}",
        "card_region": card_zone,
        "board_region": board,
        "card": round(c, 1),
        "board": round(b, 1),
        "ratio": round(ratio, 2),
        "detected": "selection" if is_sel else "normal",
    }
