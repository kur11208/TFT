"""
Board / bench slot classifier using in-domain labeled crops.

Unlike the shop matcher, this classifier expects references cropped from
the actual board/bench camera angle. It stores lightweight feature vectors
and matches by cosine similarity.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "../data/current/slot_model.json")
_DEFAULT_GROUPS = ("board", "bench")
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_SIZE = (64, 64)

_cache: Optional[dict] = None


def _normalize(vec: np.ndarray) -> np.ndarray:
    vec = vec.astype(np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def _iter_grid_means(channel: np.ndarray, rows: int, cols: int) -> list[float]:
    h, w = channel.shape[:2]
    values: list[float] = []
    y_edges = np.linspace(0, h, rows + 1, dtype=np.int32)
    x_edges = np.linspace(0, w, cols + 1, dtype=np.int32)
    for yi in range(rows):
        for xi in range(cols):
            patch = channel[y_edges[yi]:y_edges[yi + 1], x_edges[xi]:x_edges[xi + 1]]
            values.append(float(np.mean(patch)) if patch.size else 0.0)
    return values


def _prepare_image(bgr: np.ndarray) -> np.ndarray:
    if bgr is None or getattr(bgr, "size", 0) == 0:
        raise ValueError("empty image")
    return cv2.resize(bgr, _SIZE, interpolation=cv2.INTER_AREA)


def _imread_any(path: Path) -> Optional[np.ndarray]:
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
    except Exception:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def extract_slot_features(bgr: np.ndarray) -> np.ndarray:
    """
    Build a compact feature vector from an in-game slot crop.

    The vector mixes:
    - HS histogram from a center crop
    - local mean color grid
    - local saturation grid
    - local edge-density grid
    """
    img = _prepare_image(bgr)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    h, w = img.shape[:2]
    y0, y1 = int(h * 0.08), int(h * 0.92)
    x0, x1 = int(w * 0.10), int(w * 0.90)
    center = hsv[y0:y1, x0:x1]

    hs_hist = cv2.calcHist([center], [0, 1], None, [12, 8], [0, 180, 0, 256]).flatten()
    hs_hist = _normalize(hs_hist)

    edge = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 40, 120)

    bgr_grid = []
    for channel_idx in range(3):
        bgr_grid.extend(_iter_grid_means(img[:, :, channel_idx], 4, 4))
    bgr_grid = np.array(bgr_grid, dtype=np.float32) / 255.0

    sat_grid = np.array(_iter_grid_means(hsv[:, :, 1], 4, 4), dtype=np.float32) / 255.0
    edge_grid = np.array(_iter_grid_means(edge, 4, 4), dtype=np.float32) / 255.0

    features = np.concatenate([hs_hist, bgr_grid, sat_grid, edge_grid]).astype(np.float32)
    return _normalize(features)


def slot_presence_score(bgr: np.ndarray) -> float:
    """
    Heuristic occupancy score in [0, 1].

    Empty slots tend to have low saturation, low edges, and low contrast.
    """
    img = _prepare_image(bgr)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edge = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), 40, 120)

    sat = float(np.mean(hsv[:, :, 1])) / 255.0
    edge_density = float(np.mean(edge > 0))
    contrast = min(1.0, float(np.std(gray)) / 64.0)

    score = 0.45 * edge_density + 0.35 * sat + 0.20 * contrast
    return float(np.clip(score, 0.0, 1.0))


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.dot(_normalize(left), _normalize(right)))


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    _cache = {}
    if not os.path.exists(_MODEL_PATH):
        return _cache

    try:
        with open(_MODEL_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return _cache

    if not isinstance(raw, dict):
        return _cache

    parsed: dict[str, dict[str, dict[str, np.ndarray | list[np.ndarray] | int]]] = {}
    for group, labels in raw.items():
        if not isinstance(labels, dict):
            continue
        group_entries = {}
        for name, entry in labels.items():
            if not isinstance(entry, dict):
                continue
            centroid = np.array(entry.get("centroid") or [], dtype=np.float32)
            exemplars = [np.array(vec, dtype=np.float32) for vec in entry.get("exemplars") or []]
            if centroid.size == 0 or not exemplars:
                continue
            group_entries[name] = {
                "centroid": centroid,
                "exemplars": exemplars,
                "count": int(entry.get("count", len(exemplars))),
            }
        if group_entries:
            parsed[group] = group_entries
    _cache = parsed
    return _cache


def reload() -> None:
    global _cache
    _cache = None


def slot_model_available(group: Optional[str] = None) -> bool:
    model = _load()
    if group is None:
        return bool(model)
    return bool(model.get(group))


def match_slot_unit(
    bgr: np.ndarray,
    *,
    group: str,
    min_conf: float = 0.72,
    min_margin: float = 0.03,
    min_presence: float = 0.08,
    empty_margin: float = 0.02,
) -> tuple[Optional[str], float]:
    """
    Return (champion_name, similarity) for a board/bench crop.
    """
    group_model = _load().get(group)
    if not group_model:
        return None, 0.0

    presence = slot_presence_score(bgr)
    if presence < min_presence:
        return None, presence

    query = extract_slot_features(bgr)
    scored: list[tuple[str, float]] = []

    for name, entry in group_model.items():
        centroid_score = _cosine_similarity(query, entry["centroid"])
        exemplar_scores = [_cosine_similarity(query, exemplar) for exemplar in entry["exemplars"]]
        exemplar_score = max(exemplar_scores) if exemplar_scores else centroid_score
        score = 0.35 * centroid_score + 0.65 * exemplar_score
        scored.append((name, score))

    if not scored:
        return None, 0.0

    scored.sort(key=lambda item: item[1], reverse=True)
    best_name, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else -1.0

    empty_score = next((score for name, score in scored if name.lower() in {"__empty__", "empty"}), -1.0)
    if best_name.lower() in {"__empty__", "empty"}:
        return None, best_score
    if empty_score >= best_score - empty_margin:
        return None, best_score
    if best_score < min_conf:
        return None, best_score
    if best_score - second_score < min_margin:
        return None, best_score
    return best_name, best_score


def _iter_label_images(group_dir: Path) -> list[tuple[str, Path]]:
    images: list[tuple[str, Path]] = []
    if not group_dir.is_dir():
        return images
    for label_dir in sorted(group_dir.iterdir()):
        if not label_dir.is_dir() or label_dir.name.startswith("."):
            continue
        for path in sorted(label_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in _IMAGE_EXTS:
                images.append((label_dir.name, path))
    return images


def _augment_images(bgr: np.ndarray) -> list[np.ndarray]:
    variants = [bgr, cv2.flip(bgr, 1)]
    brighter = cv2.convertScaleAbs(bgr, alpha=1.0, beta=12)
    darker = cv2.convertScaleAbs(bgr, alpha=0.92, beta=-10)
    variants.extend([brighter, darker])
    unique: list[np.ndarray] = []
    seen: set[bytes] = set()
    for img in variants:
        key = img.tobytes()
        if key in seen:
            continue
        seen.add(key)
        unique.append(img)
    return unique


def build_slot_model(samples_root: str | os.PathLike[str], output_path: str | os.PathLike[str] | None = None) -> dict:
    """
    Build a model from:
      samples_root/
        board/<champion>/*.png
        bench/<champion>/*.png
    """
    root = Path(samples_root)
    groups_to_use = [group for group in _DEFAULT_GROUPS if (root / group).is_dir()]
    if not groups_to_use:
        raise FileNotFoundError(f"no board/bench sample folders found under {root}")

    model: dict[str, dict[str, dict[str, list[list[float]] | list[float] | int]]] = {}
    for group in groups_to_use:
        vectors_by_label: dict[str, list[np.ndarray]] = {}
        for label, image_path in _iter_label_images(root / group):
            img = _imread_any(image_path)
            if img is None:
                continue
            for variant in _augment_images(img):
                vectors_by_label.setdefault(label, []).append(extract_slot_features(variant))

        group_model = {}
        for label, vectors in vectors_by_label.items():
            if not vectors:
                continue
            centroid = _normalize(np.mean(np.stack(vectors, axis=0), axis=0))
            exemplars = [_normalize(vec) for vec in vectors]
            group_model[label] = {
                "count": len(exemplars),
                "centroid": centroid.tolist(),
                "exemplars": [vec.tolist() for vec in exemplars],
            }
        if group_model:
            model[group] = group_model

    if not model:
        raise ValueError(f"no usable labeled samples found under {root}")

    destination = Path(output_path or _MODEL_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
    reload()
    return model
