"""
Template-based augment card locator.

First call to save_raw() stores a raw full-resolution screenshot and extracts a
small template from the top-left frame of card 1.  Subsequent calls to
find_regions() run cv2.matchTemplate to locate the 3 cards dynamically.
Falls back to screen-fraction estimates if no template or low confidence.
"""
import cv2
import numpy as np
import os
from typing import Optional

from .regions import scale_regions_to_screen

_DATA_DIR  = os.path.join(os.path.dirname(__file__), "..", "..", "..", "screenshots", "data")
_RAW_PATH  = os.path.join(_DATA_DIR, "aug_raw.png")
_TMPL_PATH = os.path.join(_DATA_DIR, "aug_tmpl.png")

_tmpl: Optional[np.ndarray] = None

# Fractions relative to (card_width, screen_height) — tuned from ss_20260422_221708.png
# Screenshot analysis: 3 cards centred, each card ~22% of screen width,
# left edge of card-0 at ~16% of screen width, cards span ~67% of screen.
# Icons (circular art) sit in upper 55% of card; names/text below ~60%.
_ICON_X_F = 0.15   # icon left from card left edge (narrower margin observed)
_ICON_Y_F = 0.18   # icon top from screen top (cards start ~18% down from top)
_ICON_W_F = 0.70   # icon width / card width (icons are wider relative to card)
_ICON_H_F = 0.28   # icon height / screen height (icons are taller than originally tuned)
_NAME_X_F = 0.05
_NAME_Y_F = 0.54   # name text is roughly 54% down from screen top
_NAME_W_F = 0.90
_NAME_H_F = 0.08   # slightly taller name strip

# Cards span ~90% of screen width, 3 equal columns
_CARDS_SPAN_F = 0.90
# Left edge of first card ≈ 5% of screen width
_CARD0_X_F = 0.05


def _load_tmpl() -> Optional[np.ndarray]:
    global _tmpl
    if _tmpl is not None:
        return _tmpl
    if os.path.exists(_TMPL_PATH):
        _tmpl = cv2.imread(_TMPL_PATH)
    return _tmpl


def _extract_tmpl(frame: np.ndarray) -> None:
    """Cut the top-left corner of card 1 (card frame, not augment art).

    Region updated from ss_20260422_221708: card-0 starts at ~16% of screen
    width and the card top is at ~16% of screen height.  We grab the top-left
    corner of the card border (before the circular icon starts) to get a stable
    feature for template matching.
    """
    global _tmpl
    h, w = frame.shape[:2]
    # Top-left corner strip of card 1 frame (card starts ~16% from left, ~16% from top)
    x1, x2 = int(w * 0.16), int(w * 0.27)
    y1, y2 = int(h * 0.16), int(h * 0.23)
    patch = frame[y1:y2, x1:x2]
    os.makedirs(_DATA_DIR, exist_ok=True)
    cv2.imwrite(_TMPL_PATH, patch)
    _tmpl = patch


def load_from_raw() -> bool:
    """
    Extract template from aug_raw.png if it exists and no template yet.
    Call once at startup. Returns True if template was (re)loaded.
    """
    if not os.path.exists(_RAW_PATH):
        return False
    global _tmpl
    if _tmpl is not None:
        return True
    raw = cv2.imread(_RAW_PATH)
    if raw is None:
        return False
    if not os.path.exists(_TMPL_PATH):
        _extract_tmpl(raw)
    else:
        _tmpl = cv2.imread(_TMPL_PATH)
    return _tmpl is not None


def reset_template() -> None:
    """Delete saved template so next augment detection re-extracts it."""
    global _tmpl
    _tmpl = None
    for p in (_RAW_PATH, _TMPL_PATH):
        if os.path.exists(p):
            os.remove(p)


def _configured_regions(fw: int, fh: int) -> list[dict]:
    configured: list[dict] = []
    regions = scale_regions_to_screen(fw, fh)
    for i in range(1, 4):
        icon = regions.get(f"aug_icon_{i}")
        name = regions.get(f"aug_name_{i}")
        if not icon or not name:
            return []
        configured.append({
            "icon": {"x": icon["x"], "y": icon["y"], "w": icon["w"], "h": icon["h"]},
            "name": {"x": name["x"], "y": name["y"], "w": name["w"], "h": name["h"]},
        })
    return configured


def _fallback_regions(fw: int, fh: int) -> list[dict]:
    """Return estimated regions when template matching is unavailable."""
    configured = _configured_regions(fw, fh)
    if configured:
        return configured

    card_w = int(fw * _CARDS_SPAN_F / 3)
    card0_x = int(fw * _CARD0_X_F)
    icon_w = int(card_w * _ICON_W_F)
    icon_h = int(fh * _ICON_H_F)
    icon_y = int(fh * _ICON_Y_F)
    name_h = int(fh * _NAME_H_F)
    name_y = int(fh * _NAME_Y_F)
    out = []
    for i in range(3):
        cx = card0_x + i * card_w
        out.append({
            "icon": {"x": cx + int(card_w * _ICON_X_F), "y": icon_y, "w": icon_w, "h": icon_h},
            "name": {"x": cx + int(card_w * _NAME_X_F), "y": name_y, "w": int(card_w * _NAME_W_F), "h": name_h},
        })
    return out


def find_regions(frame: np.ndarray, conf_threshold: float = 0.50) -> list[dict]:
    """
    Locate 3 augment card regions.
    Returns list of 3 dicts with 'icon' and 'name' sub-dicts (x, y, w, h).
    Always returns something — falls back to fraction-based estimates.
    """
    fh, fw = frame.shape[:2]
    configured = _configured_regions(fw, fh)
    if configured:
        return configured
    tmpl = _load_tmpl()

    if tmpl is not None:
        res = cv2.matchTemplate(frame, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= conf_threshold:
            card_left = max_loc[0]
            card_w = int(fw * _CARDS_SPAN_F / 3)
            icon_w  = int(card_w * _ICON_W_F)
            icon_h  = int(fh  * _ICON_H_F)
            icon_y  = int(fh  * _ICON_Y_F)
            name_h  = int(fh  * _NAME_H_F)
            name_y  = int(fh  * _NAME_Y_F)
            out = []
            for i in range(3):
                cx = card_left + i * card_w
                out.append({
                    "icon": {"x": cx + int(card_w * _ICON_X_F), "y": icon_y, "w": icon_w, "h": icon_h},
                    "name": {"x": cx + int(card_w * _NAME_X_F), "y": name_y, "w": int(card_w * _NAME_W_F), "h": name_h},
                })
            return out

    return _fallback_regions(fw, fh)
