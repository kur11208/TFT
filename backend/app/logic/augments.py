import json
import os
from typing import List

from ..schemas import AnalyzeRequest, AugmentRecommendation, CompResult

DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/current/augments.json")


def load_augments() -> List[dict]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def calc_augment_recommendations(req: AnalyzeRequest, top_comp: CompResult) -> List[AugmentRecommendation]:
    from .comps import load_comps

    augments = load_augments()
    comps = load_comps()
    comp_data = next((c for c in comps if c["id"] == top_comp.id), None)
    comp_keywords = set(comp_data.get("augment_keywords", [])) if comp_data else set()
    board_tags = {tag for unit in req.board for tag in unit.tags}
    taken = {augment.lower() for augment in req.augments}

    tier_bonus = {"Prismatic": 5, "Gold": 3, "Silver": 0}
    scored = []

    for augment in augments:
        if augment["name"].lower() in taken:
            continue

        score = 0
        reasons: List[str] = []

        comp_matches = sum(1 for keyword in augment["keywords"] if keyword in comp_keywords)
        if comp_matches:
            score += comp_matches * 15
            reasons.append(f"{top_comp.name} と相性が良い")

        board_matches = sum(1 for keyword in augment["keywords"] if keyword in board_tags)
        if board_matches:
            score += board_matches * 8
            reasons.append("現在の盤面タグと一致")

        score += tier_bonus.get(augment["tier"], 0)

        if score > 0:
            scored.append(
                (
                    score,
                    AugmentRecommendation(
                        name=augment["name"],
                        tier=augment["tier"],
                        reason=" / ".join(reasons) if reasons else augment.get("desc", ""),
                    ),
                )
            )

    scored.sort(key=lambda entry: entry[0], reverse=True)
    return [recommendation for _, recommendation in scored[:3]]
