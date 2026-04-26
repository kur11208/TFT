"""
Augment identification: icon HSV histogram (top-N) → OCR text refinement.
Icons stored in data/augment_icons/
Mapping: data/augment_icons/mapping.json  { "日本語名": "filename.png" }
"""
import difflib
import json
import os
from typing import Optional

import cv2
import numpy as np

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "../data/augment_icons")
_MAPPING_PATH = os.path.join(_ICONS_DIR, "mapping.json")
_ICON_SIZE = (64, 64)
_TOP_N = 5

_cache: Optional[dict] = None


def _compute_hist(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [18, 16], [0, 180, 0, 256])
    cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
    return h.flatten()


def _compute_pixels(bgr: np.ndarray) -> np.ndarray:
    flat = cv2.resize(bgr, _ICON_SIZE).astype(np.float32).flatten()
    flat -= flat.mean()
    norm = np.linalg.norm(flat)
    if norm > 0:
        flat /= norm
    return flat


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    _cache = {}
    if not os.path.isdir(_ICONS_DIR) or not os.path.exists(_MAPPING_PATH):
        return _cache
    with open(_MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping: dict = json.load(f)
    for name, fname in mapping.items():
        path = os.path.join(_ICONS_DIR, fname)
        if not os.path.exists(path):
            continue
        img = cv2.imread(path)
        if img is None:
            continue
        img = cv2.resize(img, _ICON_SIZE)
        _cache[name] = {
            "hist": _compute_hist(img),
            "pixels": _compute_pixels(img),
        }
    return _cache


def reload():
    global _cache
    _cache = None


def icons_available() -> bool:
    return bool(_load())


def _top_candidates(bgr: np.ndarray) -> list[tuple[str, float]]:
    icons = _load()
    if not icons:
        return []
    query = cv2.resize(bgr, _ICON_SIZE)
    qh = _compute_hist(query)
    qp = _compute_pixels(query)
    scores = []
    for name, data in icons.items():
        hs = float(cv2.compareHist(
            data["hist"].reshape(-1, 1),
            qh.reshape(-1, 1),
            cv2.HISTCMP_CORREL,
        ))
        ps = float(np.dot(data["pixels"], qp))
        scores.append((name, 0.4 * hs + 0.6 * ps))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:_TOP_N]


def match_augment(
    icon_bgr: np.ndarray,
    ocr_text: str = "",
    min_icon_conf: float = 0.38,
) -> tuple[Optional[str], float]:
    """
    Cascade: icon match (top-N) → OCR fuzzy refinement.
    Returns (augment_name, confidence) or (None, score).
    """
    candidates = _top_candidates(icon_bgr)
    if not candidates:
        return None, 0.0

    best_name, best_score = candidates[0]

    if not ocr_text.strip():
        return (best_name, best_score) if best_score >= min_icon_conf else (None, best_score)

    # OCR refinement: fuzzy match raw text against top-N candidate names
    cand_names = [n for n, _ in candidates]
    raw = ocr_text.strip()
    matches = difflib.get_close_matches(raw, cand_names, n=1, cutoff=0.15)
    if matches:
        text_match = matches[0]
        icon_score = next((s for n, s in candidates if n == text_match), 0.0)
        text_ratio = difflib.SequenceMatcher(None, raw, text_match).ratio()
        combined = 0.65 * icon_score + 0.35 * text_ratio
        # Accept text-refined match if combined score beats raw icon top
        if combined >= min_icon_conf and combined >= best_score * 0.85:
            return text_match, combined

    return (best_name, best_score) if best_score >= min_icon_conf else (None, best_score)
