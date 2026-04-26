import json
import os
from typing import Dict, List

from ..schemas import AnalyzeRequest, BoardAdviceItem, CompResult

TRAITS_PATH = os.path.join(os.path.dirname(__file__), "../data/current/traits.json")


def _load_traits() -> List[dict]:
    with open(TRAITS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _position_label(position: str) -> str:
    return {
        "frontline": "前衛",
        "backline": "後衛",
    }.get(position, "盤面")


def calc_board_advice(req: AnalyzeRequest, top_comp: CompResult) -> List[BoardAdviceItem]:
    from .comps import load_comps

    comps = load_comps()
    comp_data = next((c for c in comps if c["id"] == top_comp.id), None)
    if not comp_data:
        return []

    advice: List[BoardAdviceItem] = []
    board_names = {u.name for u in req.board}
    bench_names = {u.name for u in req.bench}
    shop_names = {u.name for u in req.shop}

    for unit in comp_data.get("units", []):
        name = unit["name"]
        if name in board_names:
            continue

        items = unit.get("items", [])
        position_label = _position_label(unit.get("position", "flex"))
        suffix = f" 推奨アイテム: {', '.join(items[:2])}" if items else ""

        if name in bench_names:
            advice.append(
                BoardAdviceItem(
                    label=name,
                    kind="unit",
                    priority="high",
                    reason=f"ベンチにいるので、次のラウンドで{position_label}に出したい。{suffix}".strip(),
                )
            )
        elif name in shop_names:
            advice.append(
                BoardAdviceItem(
                    label=name,
                    kind="unit",
                    priority="high",
                    reason=f"ショップに見えているので、購入して{position_label}の形に寄せたい。{suffix}".strip(),
                )
            )
        else:
            advice.append(
                BoardAdviceItem(
                    label=name,
                    kind="unit",
                    priority="medium",
                    reason=f"{top_comp.name}に必要な{position_label}ユニット。見えたら優先して確保したい。{suffix}".strip(),
                )
            )

    tag_counts: Dict[str, int] = {}
    for unit in req.board:
        for tag in unit.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    for trait in _load_traits():
        trait_name = trait["name"]
        breakpoints = trait.get("breakpoints", [])
        if not breakpoints:
            continue

        current = tag_counts.get(trait_name, 0)
        if current == 0:
            continue

        next_breakpoint = next((bp for bp in breakpoints if bp > current), None)
        if next_breakpoint and next_breakpoint - current == 1:
            advice.append(
                BoardAdviceItem(
                    label=f"{trait_name} +1",
                    kind="trait",
                    priority="medium",
                    reason=f"あと1体で {trait_name} のブレークポイント {next_breakpoint} に届く。",
                )
            )

    return advice[:7]
