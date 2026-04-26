"""
Parse OCR results and annotated screenshots into AnalyzeRequest.
Also builds annotated preview images for region calibration.
"""
import base64
import difflib
import json
import os
from typing import Optional

import cv2
import numpy as np

from ..schemas import AnalyzeRequest, Unit
from .item_matcher import identify_component
from .ocr import ocr_number, ocr_stage, ocr_text
from .regions import scale_regions_to_screen
from .screenshot import capture_region, capture_full, get_screen_size
from .slot_classifier import match_slot_unit, slot_model_available
from .vision_matcher import match_portrait, icons_available, rank_portrait_candidates

_CHAMPS_PATH = os.path.join(os.path.dirname(__file__), "../data/current/champions.json")

_CHAMPION_CACHE: Optional[list] = None


def _load_champions() -> list:
    global _CHAMPION_CACHE
    if _CHAMPION_CACHE is None:
        try:
            with open(_CHAMPS_PATH, "r", encoding="utf-8") as f:
                _CHAMPION_CACHE = json.load(f)
        except Exception:
            _CHAMPION_CACHE = []
    return _CHAMPION_CACHE


def _load_champion_names() -> list[str]:
    return [c["name"] for c in _load_champions()]


def _load_champion_costs() -> dict[str, int]:
    costs: dict[str, int] = {}
    for champ in _load_champions():
        name = str(champ.get("name", "")).strip()
        if not name:
            continue
        try:
            costs[name] = int(champ.get("cost", 0))
        except (TypeError, ValueError):
            continue
    return costs


def _get_champion_tags(name: str) -> list[str]:
    for champ in _load_champions():
        if champ["name"].lower() == name.lower():
            return champ.get("tags", [])
    return []


def _fuzzy_match_champion(raw: str, known_names: list[str]) -> tuple[Optional[str], float]:
    if not raw or not known_names:
        return raw or None, 0.0
    raw_clean = raw.strip()
    matches = difflib.get_close_matches(raw_clean, known_names, n=1, cutoff=0.4)
    if matches:
        ratio = difflib.SequenceMatcher(None, raw_clean.lower(), matches[0].lower()).ratio()
        return matches[0], ratio
    return raw_clean, 0.3


def _vision_unit_slot(
    portrait_key: str,
    regions: dict,
    raw_ocr: dict,
    confidence: dict,
    *,
    min_conf: float = 0.45,
) -> Optional[Unit]:
    """Vision-based (histogram) unit detection. Returns Unit if matched, else None."""
    r = regions.get(portrait_key)
    if r is None:
        return None
    img = capture_region(r)
    name, conf = match_portrait(img, min_conf=min_conf)
    raw_ocr[portrait_key] = name or ""
    confidence[portrait_key] = conf
    if name:
        tags = _get_champion_tags(name)
        return Unit(name=name, stars=1, tags=tags)
    return None


def _slot_model_unit_slot(
    portrait_key: str,
    regions: dict,
    raw_ocr: dict,
    confidence: dict,
    *,
    group: str,
    min_conf: float,
    min_margin: float = 0.0,
) -> Optional[Unit]:
    r = regions.get(portrait_key)
    if r is None:
        return None
    img = capture_region(r)
    name, conf = match_slot_unit(img, group=group, min_conf=min_conf, min_margin=min_margin)
    raw_ocr[portrait_key] = name or ""
    confidence[portrait_key] = conf
    if name:
        tags = _get_champion_tags(name)
        return Unit(name=name, stars=1, tags=tags)
    return None


def _extract_shop_cost(key: str, regions: dict) -> Optional[int]:
    r = regions.get(key)
    if r is None:
        return None
    img = capture_region(r)
    if img is None or img.size == 0:
        return None

    width = img.shape[1]
    for trim_ratio in (0.50, 0.60, 0.35):
        digit_crop = img[:, int(width * trim_ratio):]
        value, conf = ocr_number(digit_crop, field="gold")
        if value is None or conf < 0.35:
            continue
        for ch in reversed(str(value)):
            digit = int(ch)
            if 1 <= digit <= 5:
                return digit
    return None


def _vision_shop_slot(
    slot_index: int,
    regions: dict,
    raw_ocr: dict,
    confidence: dict,
) -> Optional[Unit]:
    portrait_key = f"portrait_shop_{slot_index}"
    r = regions.get(portrait_key)
    if r is None:
        return None

    img = capture_region(r)
    candidates = rank_portrait_candidates(img, top_n=5, crop_ratio=1.0)
    overall_name = candidates[0][0] if candidates else ""
    overall_conf = candidates[0][1] if candidates else 0.0
    best_name = overall_name
    best_conf = overall_conf
    matched_name: Optional[str] = None
    matched_conf = 0.0

    detected_cost = _extract_shop_cost(f"shop_{slot_index}", regions)
    champion_costs = _load_champion_costs()
    if detected_cost is not None:
        raw_ocr[f"shop_cost_{slot_index}"] = str(detected_cost)
        confidence[f"shop_cost_{slot_index}"] = 0.5
        cost_candidates = [
            (name, score)
            for name, score in candidates
            if champion_costs.get(name) == detected_cost
        ]
        if cost_candidates:
            cost_name, cost_conf = cost_candidates[0]
            cost_margin = cost_conf - (cost_candidates[1][1] if len(cost_candidates) > 1 else 0.0)

            if (
                cost_conf >= 0.30
                and cost_conf >= overall_conf - 0.025
                and (cost_conf >= 0.36 or cost_margin >= 0.04 or overall_conf < 0.40)
            ):
                matched_name = cost_name
                matched_conf = cost_conf
                best_name, best_conf = cost_name, cost_conf

    if matched_name is None and candidates:
        best_name, best_conf = overall_name, overall_conf
        if overall_conf >= 0.40:
            matched_name = overall_name
            matched_conf = overall_conf
        elif best_conf >= 0.36 and detected_cost is not None and champion_costs.get(best_name) == detected_cost:
            matched_name = best_name
            matched_conf = best_conf

    raw_ocr[portrait_key] = matched_name or ""
    confidence[portrait_key] = matched_conf if matched_name else best_conf
    if matched_name:
        tags = _get_champion_tags(matched_name)
        return Unit(name=matched_name, stars=1, tags=tags)
    return None


def _ocr_unit_slot(key: str, regions: dict, known_names: list[str],
                   raw_ocr: dict, confidence: dict) -> Optional[Unit]:
    """OCR a single unit slot (board or bench). Returns Unit if matched, else None."""
    r = regions.get(key)
    if r is None:
        return None
    img = capture_region(r)
    text, conf = ocr_text(img)
    if not text or conf < 0.25:
        return None
    matched, match_conf = _fuzzy_match_champion(text, known_names)
    raw_ocr[key] = text
    confidence[key] = match_conf
    if matched and match_conf >= 0.45:
        tags = _get_champion_tags(matched)
        return Unit(name=matched, stars=1, tags=tags)
    return None


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = value.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped


def _prefer_detected_units(new_units: list[Unit], old_units: list[Unit], *, min_ratio: float) -> list[Unit]:
    if not new_units:
        return old_units
    if not old_units:
        return new_units
    minimum_needed = max(1, int(np.ceil(len(old_units) * min_ratio)))
    return new_units if len(new_units) >= minimum_needed else old_units


def _stage_to_index(stage: str) -> Optional[int]:
    try:
        stage_num, round_num = (int(part) for part in stage.split("-", 1))
    except Exception:
        return None
    if not (1 <= stage_num <= 9 and 1 <= round_num <= 7):
        return None
    return stage_num * 10 + round_num


def _pick_stage(new_stage: Optional[str], old_stage: str, stage_confidence: float, *, default_stage: str) -> str:
    if not new_stage:
        return old_stage
    if old_stage == default_stage:
        return new_stage if stage_confidence >= 0.35 else old_stage
    if stage_confidence < 0.52:
        return old_stage

    new_idx = _stage_to_index(new_stage)
    old_idx = _stage_to_index(old_stage)
    if new_idx is None or old_idx is None:
        return old_stage

    delta = new_idx - old_idx
    if 0 <= delta <= 7:
        return new_stage
    if delta == -1 and stage_confidence >= 0.72:
        return new_stage
    if stage_confidence >= 0.82:
        return new_stage
    return old_stage


def capture_game_state(existing: Optional[AnalyzeRequest] = None) -> dict:
    """
    Capture screen, OCR each region, and return:
      { "state": AnalyzeRequest, "raw_ocr": dict, "confidence": dict }
    existing: fields with confidence below threshold are kept from this.
    """
    known_names = _load_champion_names()
    sw, sh = get_screen_size()
    regions = scale_regions_to_screen(sw, sh)

    raw_ocr: dict[str, str] = {}
    confidence: dict[str, float] = {}

    # --- Numeric fields ---
    for field in ("level", "hp", "gold"):
        r = regions.get(field)
        if r is None:
            continue
        img = capture_region(r)
        val, conf = ocr_number(img, field=field)
        raw_ocr[field] = str(val) if val is not None else ""
        confidence[field] = conf

    # --- Stage text ---
    stage_region = regions.get("stage")
    stage_conf = 0.0
    if stage_region is not None:
        stage_img = capture_region(stage_region)
        expected_stage = existing.stage if existing is not None else None
        parsed_stage, stage_conf = ocr_stage(stage_img, expected_stage=expected_stage)
        raw_ocr["stage"] = parsed_stage or ""
        confidence["stage"] = stage_conf if parsed_stage else 0.0

    use_vision = icons_available()
    use_board_slot_model = slot_model_available("board")
    use_bench_slot_model = slot_model_available("bench")

    # --- Shop slots ---
    shop_units: list[Unit] = []
    for i in range(1, 6):
        unit = (
            _vision_shop_slot(i, regions, raw_ocr, confidence)
            if use_vision else
            _ocr_unit_slot(f"shop_{i}", regions, known_names, raw_ocr, confidence)
        )
        if unit:
            shop_units.append(unit)

    # --- Board slots (4 rows x 7 cols, r1=back r4=front) ---
    board_units: list[Unit] = []
    for row in range(1, 5):
        for col in range(1, 8):
            if use_board_slot_model:
                unit = _slot_model_unit_slot(
                    f"portrait_board_r{row}_c{col}",
                    regions,
                    raw_ocr,
                    confidence,
                    group="board",
                    min_conf=0.74,
                    min_margin=0.0,
                )
            else:
                unit = (
                    _vision_unit_slot(
                    f"portrait_board_r{row}_c{col}",
                    regions,
                    raw_ocr,
                    confidence,
                    min_conf=0.60,
                )
                    if use_vision else
                    _ocr_unit_slot(f"board_r{row}_c{col}", regions, known_names, raw_ocr, confidence)
                )
            if unit:
                if use_board_slot_model or unit.name not in {u.name for u in board_units}:
                    board_units.append(unit)

    # --- Bench slots ---
    bench_units: list[Unit] = []
    for i in range(1, 10):
        if use_bench_slot_model:
            unit = _slot_model_unit_slot(
                f"portrait_bench_{i}",
                regions,
                raw_ocr,
                confidence,
                group="bench",
                min_conf=0.74,
                min_margin=0.0,
            )
        else:
            unit = (
                _vision_unit_slot(
                f"portrait_bench_{i}",
                regions,
                raw_ocr,
                confidence,
                min_conf=0.52,
            )
            if use_vision else
            _ocr_unit_slot(f"bench_{i}", regions, known_names, raw_ocr, confidence)
            )
        if unit:
            if use_bench_slot_model or unit.name not in {u.name for u in bench_units}:
                bench_units.append(unit)

    # --- Item bench (テンプレートマッチング) ---
    item_names: list[str] = []
    for i in range(1, 11):
        key = f"item_{i}"
        r = regions.get(key)
        if r is None:
            continue
        img = capture_region(r)
        component = identify_component(img)
        raw_ocr[key] = component or ""
        confidence[key] = 0.55 if component else 0.0
        if component:
            item_names.append(component)
    item_names = _dedupe_strings(item_names)
    raw_ocr["items"] = ", ".join(item_names)
    confidence["items"] = 0.55 if item_names else 0.0

    # --- Merge with existing (keep existing value when OCR confidence is low) ---
    CONF_THRESHOLD = 0.4

    def pick(field: str, new_val, old_val):
        if new_val is not None and confidence.get(field, 0.0) >= CONF_THRESHOLD:
            return new_val
        return old_val

    base = existing or AnalyzeRequest()
    base_defaults = AnalyzeRequest()
    state = AnalyzeRequest(
        patch=base.patch,
        stage=_pick_stage(raw_ocr.get("stage") or None, base.stage, stage_conf, default_stage=base_defaults.stage),
        level=base.level if base.level != base_defaults.level else pick("level", int(raw_ocr["level"]) if raw_ocr.get("level") else None, base.level),
        hp=pick("hp", int(raw_ocr["hp"]) if raw_ocr.get("hp") else None, base.hp),
        gold=pick("gold", int(raw_ocr["gold"]) if raw_ocr.get("gold") else None, base.gold),
        streak=base.streak,
        board=_prefer_detected_units(board_units, base.board, min_ratio=0.5),
        bench=_prefer_detected_units(bench_units, base.bench, min_ratio=0.5),
        shop=_prefer_detected_units(shop_units, base.shop, min_ratio=0.6),
        items=base.items if base.items else item_names,
        augments=base.augments,
        notes=base.notes,
    )

    return {
        "state": state,
        "raw_ocr": raw_ocr,
        "confidence": confidence,
    }


# --- Preview image ---

_REGION_COLORS = {
    "stage":  (0, 255, 255),
    "level":  (0, 200, 255),
    "hp":     (0, 80, 255),
    "gold":   (50, 200, 50),
    "shop_1": (255, 160, 0),
    "shop_2": (255, 160, 0),
    "shop_3": (255, 160, 0),
    "shop_4": (255, 160, 0),
    "shop_5": (255, 160, 0),
}

def _region_color(name: str) -> tuple:
    if name in _REGION_COLORS:
        return _REGION_COLORS[name]
    if name.startswith("board_"):
        return (200, 80, 255)
    if name.startswith("bench_"):
        return (80, 200, 255)
    return (200, 200, 200)


def build_preview_image(raw_ocr: dict, confidence: dict) -> str:
    sw, sh = get_screen_size()
    regions = scale_regions_to_screen(sw, sh)
    img = capture_full()

    for name, r in regions.items():
        color = _region_color(name)
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        label = raw_ocr.get(name, "")
        conf = confidence.get(name, 0.0)
        display = f"{name}: '{label}' ({conf:.0%})" if label else name
        (tw, th), _ = cv2.getTextSize(display, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.rectangle(img, (x, y - th - 6), (x + tw + 4, y), (20, 20, 20), -1)
        cv2.putText(img, display, (x + 2, y - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

    if sw > 1280:
        scale = 1280 / sw
        img = cv2.resize(img, (1280, int(sh * scale)))

    _, buf = cv2.imencode(".png", img)
    return base64.b64encode(buf).decode("utf-8")
