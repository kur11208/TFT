"""
Champion portrait matching via HSV histogram + normalized pixel correlation.
Icons stored in data/champion_icons/{filename}.png
Mapping: data/champion_icons/mapping.json { "localized_name": "filename.png" }
"""
import json
import os
from typing import Iterable, Optional

import cv2
import numpy as np

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "../data/champion_icons")
_MAPPING_PATH = os.path.join(_ICONS_DIR, "mapping.json")
_ICON_SIZE = (64, 64)

_cache: Optional[dict] = None  # name -> {"hist", "pixels"}


def _center_crop(img: np.ndarray, ratio: float = 0.72) -> np.ndarray:
    """Crop center region to reduce cost-border / frame noise."""
    h, w = img.shape[:2]
    cy, cx = h // 2, w // 2
    ch = max(1, int(h * ratio / 2))
    cw = max(1, int(w * ratio / 2))
    return img[cy - ch:cy + ch, cx - cw:cx + cw]


def _compute_hist(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [18, 16], [0, 180, 0, 256])
    cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
    return h.flatten()


def _compute_pixels(bgr: np.ndarray) -> np.ndarray:
    """Mean-centered, L2-normalized pixel vector for cross-correlation."""
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


def is_empty(bgr: np.ndarray) -> bool:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    mean_val = float(np.mean(gray))
    max_val = float(np.max(gray))
    # Require both mean and max to be dark to avoid rejecting dark-art champs.
    return mean_val < 35.0 and max_val < 70


def _score_candidates(
    query_hist: np.ndarray,
    query_pixels: np.ndarray,
    *,
    allowed_names: Optional[Iterable[str]] = None,
) -> list[tuple[str, float]]:
    icons = _load()
    allowed = set(allowed_names) if allowed_names is not None else None
    scores: list[tuple[str, float]] = []

    for name, data in icons.items():
        if allowed is not None and name not in allowed:
            continue
        hist_score = float(
            cv2.compareHist(
                data["hist"].reshape(-1, 1),
                query_hist.reshape(-1, 1),
                cv2.HISTCMP_CORREL,
            )
        )
        pixel_score = float(np.dot(data["pixels"], query_pixels))
        combined = 0.35 * hist_score + 0.65 * pixel_score
        scores.append((name, combined))

    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def rank_portrait_candidates(
    bgr: np.ndarray,
    *,
    allowed_names: Optional[Iterable[str]] = None,
    top_n: int = 5,
    crop_ratio: float = 0.72,
) -> list[tuple[str, float]]:
    icons = _load()
    if not icons or is_empty(bgr):
        return []

    cropped = bgr if crop_ratio >= 0.99 else _center_crop(bgr, ratio=crop_ratio)
    if cropped.size == 0:
        cropped = bgr
    query_img = cv2.resize(cropped, _ICON_SIZE)

    query_hist = _compute_hist(query_img)
    query_pixels = _compute_pixels(query_img)
    return _score_candidates(query_hist, query_pixels, allowed_names=allowed_names)[:top_n]


def match_portrait(
    bgr: np.ndarray,
    min_conf: float = 0.45,
    *,
    allowed_names: Optional[Iterable[str]] = None,
    crop_ratio: float = 0.72,
) -> tuple[Optional[str], float]:
    """
    Compare bgr portrait against loaded icons.
    Uses weighted combination of HSV histogram correlation (35%) and
    normalized pixel cross-correlation (65%) for better discrimination.
    Returns (champion_name, confidence) or (None, score) if below threshold.
    """
    candidates = rank_portrait_candidates(
        bgr,
        allowed_names=allowed_names,
        top_n=1,
        crop_ratio=crop_ratio,
    )
    if not candidates:
        return None, 0.0

    best_name, best_score = candidates[0]
    if best_score < min_conf:
        return None, best_score
    return best_name, best_score
