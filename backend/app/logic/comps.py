import json
import os
from typing import List, Tuple

from ..schemas import AnalyzeRequest, CompResult, CompUnit
from .item_advisor import canonicalize_item_name

DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/current/comps.json")


def load_comps() -> List[dict]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _item_matches_keywords(item_name: str, item_keywords: List[str]) -> bool:
    text = canonicalize_item_name(item_name).lower()
    raw = str(item_name or "").lower()
    return any(
        keyword.lower() in text
        or text in keyword.lower()
        or keyword.lower() in raw
        or raw in keyword.lower()
        for keyword in item_keywords
    )


def score_comp(comp: dict, req: AnalyzeRequest) -> Tuple[int, str]:
    score = 0
    reasons: List[str] = []

    all_units = req.board + req.bench + req.shop
    all_tags = [tag for unit in all_units for tag in unit.tags]

    key_tags = set(comp.get("key_tags", []))
    frontline_tags = set(comp.get("frontline_tags", []))
    item_keywords: List[str] = comp.get("item_keywords", [])
    augment_keywords: List[str] = comp.get("augment_keywords", [])
    held_items = req.items
    equipped_items = [item for unit in (req.board + req.bench) for item in unit.items]

    matching_tags = sum(1 for tag in all_tags if tag in key_tags)
    tag_score = min(matching_tags * 8, 40)
    score += tag_score
    if matching_tags > 0:
        reasons.append(f"主要タグ一致 {matching_tags}")

    frontline_matches = sum(1 for tag in all_tags if tag in frontline_tags)
    score += min(frontline_matches * 4, 12)
    if frontline_matches > 0:
        reasons.append(f"前衛タグ一致 {frontline_matches}")

    held_item_matches = sum(1 for item in held_items if _item_matches_keywords(item, item_keywords))
    equipped_item_matches = sum(1 for item in equipped_items if _item_matches_keywords(item, item_keywords))
    score += held_item_matches * 8
    score += equipped_item_matches * 10
    if held_item_matches or equipped_item_matches:
        reasons.append(f"アイテム相性 {held_item_matches + equipped_item_matches}")

    augment_matches = sum(
        1 for augment in req.augments if any(keyword.lower() in augment.lower() for keyword in augment_keywords)
    )
    score += augment_matches * 10
    if augment_matches > 0:
        reasons.append(f"オーグメント相性 {augment_matches}")

    min_level = comp.get("min_level", 6)
    if req.level >= min_level:
        score += 10
        reasons.append(f"必要レベル到達済み Lv{req.level}")
    else:
        diff = min_level - req.level
        if diff <= 2:
            score += 5
            reasons.append(f"必要レベルまであと {diff}")

    if not reasons:
        reasons.append("現状の盤面との直接的な一致は薄い")

    return min(score, 100), " / ".join(reasons)


def calc_top_comp(req: AnalyzeRequest) -> CompResult:
    comps = load_comps()
    best_comp = comps[0]
    best_score = -1
    best_reason = ""
    preferred = getattr(req, "preferred_comp_id", None) or ""

    for comp in comps:
        score, reason = score_comp(comp, req)
        if comp["id"] == preferred:
            score += 20
            reason = f"手動指定ボーナス / {reason}" if reason else "手動指定ボーナス"
        if score > best_score:
            best_score = score
            best_comp = comp
            best_reason = reason

    return CompResult(
        id=best_comp["id"],
        name=best_comp["name"],
        score=best_score,
        reason=best_reason,
        tier=best_comp.get("tier", "B"),
        win_rate=best_comp.get("win_rate", 0.0),
        top4_rate=best_comp.get("top4_rate", 0.0),
        avg_placement=best_comp.get("avg_placement", 4.5),
        difficulty=best_comp.get("difficulty", "Medium"),
        play_style=best_comp.get("play_style", ""),
        when_to_play=best_comp.get("when_to_play", ""),
        carry=best_comp.get("carry", ""),
        units=[CompUnit(**unit) for unit in best_comp.get("units", [])],
        early_board=best_comp.get("early_board", []),
    )
