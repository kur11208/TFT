"""
Forge component picker, augment choice advisor, and situation advisor.
"""
import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

_AUGMENTS_PATH = os.path.join(os.path.dirname(__file__), "../data/current/augments.json")
_COMPS_PATH    = os.path.join(os.path.dirname(__file__), "../data/current/comps.json")

# ---- 正規化エイリアス（ゲーム内日本語表記 ↔ 内部キー） ----
ALIASES: Dict[str, str] = {
    # 長い表記 → 短い表記
    "ニードレスリー・ラージ・ロッド": "ロッド",
    "needlessly large rod": "ロッド", "nl rod": "ロッド", "rod": "ロッド",
    "ティア・オブ・ゴッデス": "涙",
    "tear of the goddess": "涙", "tear": "涙",
    "bfソード": "BFソード", "bf sword": "BFソード", "b.f.": "BFソード", "sword": "BFソード",
    "剣": "BFソード",
    "リカーブボウ": "リカーブボウ", "recurve bow": "リカーブボウ", "bow": "リカーブボウ", "弓": "リカーブボウ",
    "スパーリンググローブ": "グローブ", "sparring gloves": "グローブ", "glove": "グローブ", "グローブ": "グローブ",
    "チェーンベスト": "チョッキ", "chain vest": "チョッキ", "vest": "チョッキ", "チョッキ": "チョッキ",
    "ジャイアンツ・ベルト": "ベルト", "giant's belt": "ベルト", "giants belt": "ベルト", "belt": "ベルト", "ベルト": "ベルト",
    "ネガトロン・クローク": "クローク", "negatron cloak": "クローク", "cloak": "クローク",
    "チェーン": "クローク", "マント": "クローク",
    "スパチュラ": "スパチュラ", "spatula": "スパチュラ", "へら": "スパチュラ",
    "ロッド": "ロッド", "涙": "涙",
}

# ゲーム内表記（UIに表示する正式名）
COMPONENT_DISPLAY = {
    "ロッド":    "ニードレスリー・ラージ・ロッド",
    "涙":        "ティア・オブ・ゴッデス",
    "BFソード":  "BFソード",
    "リカーブボウ":"リカーブボウ",
    "グローブ":  "スパーリンググローブ",
    "チョッキ":  "チェーンベスト",
    "ベルト":    "ジャイアンツ・ベルト",
    "クローク":  "ネガトロン・クローク",
    "スパチュラ":"スパチュラ",
}

ALL_COMPONENT_KEYS = list(COMPONENT_DISPLAY.keys())

# ---- コンポーネントコンボ → 完成アイテム名 ----
COMBOS: Dict[frozenset, str] = {
    frozenset(["BFソード",    "BFソード"]):    "デスブレード",
    frozenset(["BFソード",    "リカーブボウ"]):"ギンソーのレイジブレード",
    frozenset(["BFソード",    "グローブ"]):    "インフィニティ・エッジ",
    frozenset(["BFソード",    "チョッキ"]):    "ブラッドサースター",
    frozenset(["BFソード",    "ベルト"]):      "ステラックの篭手",
    frozenset(["BFソード",    "涙"]):          "ヘクステック・ガンブレード",
    frozenset(["BFソード",    "クローク"]):    "クイックシルバー",
    frozenset(["BFソード",    "ロッド"]):      "ナイトの縁",

    frozenset(["リカーブボウ","リカーブボウ"]):"ラピッドファイア・キャノン",
    frozenset(["リカーブボウ","グローブ"]):    "ラスト・ウィスパー",
    frozenset(["リカーブボウ","チョッキ"]):    "サンファイア・ケープ",
    frozenset(["リカーブボウ","ベルト"]):      "タイタンの決意",
    frozenset(["リカーブボウ","涙"]):          "ナッシャーの歯牙",

    frozenset(["ロッド",      "ロッド"]):      "ラバドンのデスキャップ",
    frozenset(["ロッド",      "涙"]):          "ブルーバフ",
    frozenset(["ロッド",      "グローブ"]):    "ジュエルド・ガントレット",
    frozenset(["ロッド",      "チョッキ"]):    "アイオニック・スパーク",
    frozenset(["ロッド",      "ベルト"]):      "リデンプション",
    frozenset(["ロッド",      "クローク"]):    "ドラゴンクロウ",

    frozenset(["涙",          "涙"]):          "蒼者の穂先",
    frozenset(["涙",          "グローブ"]):    "クイックシルバー",
    frozenset(["涙",          "チョッキ"]):    "リデンプション",
    frozenset(["涙",          "ベルト"]):      "リデンプション",
    frozenset(["涙",          "クローク"]):    "パワーのチャリス",

    frozenset(["グローブ",    "グローブ"]):    "ティアマット",
    frozenset(["グローブ",    "チョッキ"]):    "ソーンメイル",
    frozenset(["グローブ",    "ベルト"]):      "ステラックの篭手（Crit）",
    frozenset(["グローブ",    "クローク"]):    "フローズンハート",

    frozenset(["チョッキ",    "チョッキ"]):    "ガーゴイル・ストーンプレート",
    frozenset(["チョッキ",    "ベルト"]):      "サンファイア・ケープ",
    frozenset(["チョッキ",    "クローク"]):    "ソーンメイル",

    frozenset(["ベルト",      "ベルト"]):      "ウォーモグのアーマー",
    frozenset(["ベルト",      "クローク"]):    "フローズンハート",

    frozenset(["クローク",    "クローク"]):    "ドラゴンクロウ",
}

# 完成アイテム → キーワードタグ（構成 item_keywords とのマッチに使う）
ITEM_TAGS: Dict[str, List[str]] = {
    "デスブレード":              ["BFソード", "剣", "AD", "Sword", "Deathblade"],
    "ギンソーのレイジブレード":  ["リカーブボウ", "BFソード", "弓", "AD", "AS", "攻撃速度", "ギンソー", "Rageblade"],
    "インフィニティ・エッジ":    ["BFソード", "剣", "クリティカル", "AD", "Crit", "インフィニティ", "Infinity"],
    "ブラッドサースター":        ["BFソード", "剣", "AD", "吸血", "Bloodthirster"],
    "ステラックの篭手":          ["BFソード", "剣", "AD", "HP", "Sterak"],
    "ヘクステック・ガンブレード":["BFソード", "剣", "涙", "AD", "AP", "Gunblade"],
    "クイックシルバー":          ["BFソード", "剣", "クローク", "AD", "Quicksilver"],
    "ナイトの縁":                ["BFソード", "剣", "ロッド", "AD", "AP"],
    "ラピッドファイア・キャノン":["リカーブボウ", "弓", "AS", "攻撃速度", "射程", "ラピッドファイア", "Rapidfire"],
    "ラスト・ウィスパー":        ["リカーブボウ", "弓", "AD", "Crit", "クリティカル", "ラスト・ウィスパー", "Last Whisper"],
    "サンファイア・ケープ":      ["チョッキ", "ベルト", "Tank", "タンク", "HP", "Sunfire"],
    "タイタンの決意":            ["リカーブボウ", "弓", "ベルト", "HP", "AS"],
    "ラバドンのデスキャップ":    ["ロッド", "AP", "魔力", "Rabadon", "デスキャップ"],
    "ブルーバフ":                ["ロッド", "涙", "AP", "マナ", "Blue Buff", "ブルーバフ"],
    "ジュエルド・ガントレット":  ["ロッド", "グローブ", "AP", "Crit", "クリティカル", "Jeweled Gauntlet", "ジュエルド"],
    "アイオニック・スパーク":    ["ロッド", "チョッキ", "AP", "Tank", "タンク"],
    "リデンプション":            ["涙", "ベルト", "回復", "HP", "Redemption"],
    "ドラゴンクロウ":            ["クローク", "チェーン", "Tank", "タンク", "MR", "Dragon's Claw", "ドラゴンクロウ"],
    "蒼者の穂先":                ["涙", "AP", "マナ", "蒼者", "Spear of Shojin"],
    "パワーのチャリス":          ["涙", "クローク", "AP", "MR", "チャリス"],
    "ガーゴイル・ストーンプレート":["チョッキ", "Tank", "タンク", "Armor", "鎧", "Gargoyle", "ガーゴイル"],
    "ウォーモグのアーマー":      ["ベルト", "Tank", "タンク", "HP", "Warmog", "ウォーモグ"],
    "ソーンメイル":              ["チョッキ", "クローク", "Tank", "タンク", "Armor", "Thornmail", "ソーンメイル"],
}


def _clean_item_text(value: str) -> str:
    return re.sub(r"[\s・･'’`´\-‐‑‒–—_./]+", "", str(value or "")).lower()


def _build_component_aliases() -> tuple[Dict[str, str], List[tuple[str, str]]]:
    exact: Dict[str, str] = {}
    searchable: List[tuple[str, str]] = []

    for alias, canonical in ALIASES.items():
        cleaned = _clean_item_text(alias)
        if not cleaned:
            continue
        exact[cleaned] = canonical
        if len(cleaned) >= 4:
            searchable.append((cleaned, canonical))

    for canonical, display in COMPONENT_DISPLAY.items():
        for alias in (canonical, display):
            cleaned = _clean_item_text(alias)
            if not cleaned:
                continue
            exact[cleaned] = canonical
            if len(cleaned) >= 4:
                searchable.append((cleaned, canonical))

    searchable.sort(key=lambda item: len(item[0]), reverse=True)
    return exact, searchable


def _build_full_item_aliases() -> tuple[Dict[str, str], List[tuple[str, str]]]:
    exact: Dict[str, str] = {}
    searchable: List[tuple[str, str]] = []

    for full_item, tags in ITEM_TAGS.items():
        aliases = [full_item] + list(tags)
        for alias in aliases:
            cleaned = _clean_item_text(alias)
            if len(cleaned) < 4:
                continue
            exact.setdefault(cleaned, full_item)
            searchable.append((cleaned, full_item))

    searchable.sort(key=lambda item: len(item[0]), reverse=True)
    return exact, searchable


def _combo_parts(key: frozenset) -> Tuple[str, str]:
    values = list(key)
    if len(values) == 1:
        return values[0], values[0]
    values.sort()
    return values[0], values[1]


_COMPONENT_EXACT_ALIASES, _COMPONENT_SEARCH_ALIASES = _build_component_aliases()
_FULL_ITEM_EXACT_ALIASES, _FULL_ITEM_SEARCH_ALIASES = _build_full_item_aliases()
FULL_ITEM_COMPONENTS: Dict[str, Tuple[str, str]] = {
    full_name: _combo_parts(parts)
    for parts, full_name in COMBOS.items()
}


def _normalize(name: str) -> str:
    return ALIASES.get(name.strip().lower(), ALIASES.get(name.strip(), name.strip()))


def canonicalize_item_name(name: str) -> str:
    raw = str(name or "").strip()
    if not raw:
        return ""

    norm = _normalize(raw)
    if norm in COMPONENT_DISPLAY:
        return norm

    cleaned = _clean_item_text(raw)
    if not cleaned:
        return raw

    component = _COMPONENT_EXACT_ALIASES.get(cleaned)
    if component:
        return component

    full_item = _FULL_ITEM_EXACT_ALIASES.get(cleaned)
    if full_item:
        return full_item

    for alias, canonical in _COMPONENT_SEARCH_ALIASES:
        if alias in cleaned or cleaned in alias:
            return canonical

    for alias, canonical in _FULL_ITEM_SEARCH_ALIASES:
        if alias in cleaned or cleaned in alias:
            return canonical

    return raw


def _display_item_name(name: str) -> str:
    canonical = canonicalize_item_name(name)
    return canonical or str(name or "").strip()


def _unit_name(unit: Any) -> str:
    if isinstance(unit, dict):
        return str(unit.get("name") or "")
    return str(getattr(unit, "name", "") or "")


def _unit_stars(unit: Any) -> int:
    if isinstance(unit, dict):
        return int(unit.get("stars") or 1)
    return int(getattr(unit, "stars", 1) or 1)


def _unit_items(unit: Any) -> List[str]:
    if isinstance(unit, dict):
        items = unit.get("items") or []
    else:
        items = getattr(unit, "items", []) or []
    return [str(item).strip() for item in items if str(item).strip()]


def _find_state_unit(state: Any, unit_name: str) -> tuple[str, Any] | tuple[None, None]:
    candidates: List[tuple[int, int, str, Any]] = []
    for location in ("board", "bench"):
        for unit in getattr(state, location, []) or []:
            if _unit_name(unit) != unit_name:
                continue
            rank = 0 if location == "board" else 1
            candidates.append((rank, -_unit_stars(unit), location, unit))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: (item[0], item[1]))
    _, _, location, unit = candidates[0]
    return location, unit


def _format_item_list(items: List[str], separator: str = " / ") -> str:
    return separator.join(_display_item_name(item) for item in items if item)


def _build_target_item_state(
    name: str,
    ideal_items: List[str],
    location: Optional[str],
    unit: Any,
    held_components: Counter,
    held_full_items: Counter,
) -> Dict[str, Any]:
    ideal = [canonicalize_item_name(item) for item in ideal_items if canonicalize_item_name(item)]
    equipped = [canonicalize_item_name(item) for item in _unit_items(unit) if canonicalize_item_name(item)]

    equipped_counter = Counter(equipped)
    matched: List[str] = []
    missing: List[str] = []
    remaining_equipped = equipped_counter.copy()
    for item in ideal:
        if remaining_equipped[item] > 0:
            matched.append(item)
            remaining_equipped[item] -= 1
        else:
            missing.append(item)

    goal_counter = Counter(ideal)
    off_plan: List[str] = []
    for item in equipped:
        if goal_counter[item] > 0:
            goal_counter[item] -= 1
        else:
            off_plan.append(item)

    available_components = held_components.copy()
    available_full_items = held_full_items.copy()
    ready_to_equip: List[str] = []
    craftable_now: List[Dict[str, Any]] = []
    next_goal: Optional[Dict[str, Any]] = None

    for item in missing:
        if available_full_items[item] > 0:
            available_full_items[item] -= 1
            ready_to_equip.append(item)
            continue

        parts = FULL_ITEM_COMPONENTS.get(item)
        if parts:
            needed = Counter(parts)
            if all(available_components[part] >= count for part, count in needed.items()):
                for part, count in needed.items():
                    available_components[part] -= count
                craftable_now.append({"item": item, "components": list(parts)})
                continue
            if next_goal is None:
                missing_parts: List[str] = []
                for part, count in needed.items():
                    shortage = max(0, count - available_components[part])
                    missing_parts.extend([part] * shortage)
                next_goal = {
                    "item": item,
                    "components": list(parts),
                    "missing_components": missing_parts,
                }
        elif next_goal is None:
            next_goal = {"item": item, "components": [], "missing_components": []}

    return {
        "name": name,
        "location": location or "missing",
        "equipped_items": equipped,
        "ideal_items": ideal,
        "matched_items": matched,
        "missing_items": missing,
        "off_plan_items": off_plan,
        "ready_to_equip": ready_to_equip,
        "craftable_now": craftable_now,
        "next_goal": next_goal,
        "slots_full": len(equipped) >= 3,
    }


def build_item_advice_context(state: Any, comp_id: str) -> Dict[str, Any]:
    comp = _load_comp_data(comp_id)
    if not comp:
        return {}

    held_items = [canonicalize_item_name(item) for item in getattr(state, "items", []) or [] if canonicalize_item_name(item)]
    held_components = Counter(item for item in held_items if item in COMPONENT_DISPLAY)
    held_full_items = Counter(item for item in held_items if item and item not in COMPONENT_DISPLAY)

    carry_name = comp.get("carry", "")
    comp_units = comp.get("units", [])
    carry_plan = next((unit for unit in comp_units if unit.get("name") == carry_name), None)

    frontline_units = [unit for unit in comp_units if unit.get("position") == "frontline"]
    tank_plan = next((unit for unit in frontline_units if unit.get("items")), frontline_units[0] if frontline_units else None)

    carry_location, carry_unit = _find_state_unit(state, carry_name) if carry_name else (None, None)
    tank_location, tank_unit = _find_state_unit(state, tank_plan.get("name", "")) if tank_plan else (None, None)

    context: Dict[str, Any] = {
        "comp": comp,
        "held_items": held_items,
        "held_components": held_components,
        "held_full_items": held_full_items,
    }

    if carry_plan:
        context["carry"] = _build_target_item_state(
            carry_name,
            carry_plan.get("items", []),
            carry_location,
            carry_unit,
            held_components,
            held_full_items,
        )

    if tank_plan:
        context["tank"] = _build_target_item_state(
            tank_plan.get("name", ""),
            tank_plan.get("items", []),
            tank_location,
            tank_unit,
            held_components,
            held_full_items,
        )

    return context


def _build_target_item_action(target: Dict[str, Any], *, primary: bool) -> Optional[Dict[str, str]]:
    if not target:
        return None

    name = target["name"]
    equipped = target["equipped_items"]
    ideal = target["ideal_items"]
    current_text = _format_item_list(equipped) if equipped else "未装備"
    ideal_text = _format_item_list(ideal) if ideal else "指定なし"

    if primary and target["location"] == "bench":
        return {
            "priority": "high",
            "action": f"出す: {name}を盤面へ",
            "detail": f"主キャリー。装備: {current_text} / 目標: {ideal_text}",
        }

    if target["ready_to_equip"]:
        item = target["ready_to_equip"][0]
        return {
            "priority": "high" if primary else "medium",
            "action": f"装備: {name}に{item}",
            "detail": f"手持ち完成品を載せる。現在: {current_text}",
        }

    if target["craftable_now"] and not target["slots_full"]:
        craft = target["craftable_now"][0]
        parts_text = " + ".join(_display_item_name(part) for part in craft["components"])
        return {
            "priority": "high" if primary else "medium",
            "action": f"作る: {name}に{craft['item']}",
            "detail": f"素材: {parts_text} / 現在: {current_text}",
        }

    next_goal = target["next_goal"]
    if next_goal and target["missing_items"] and not target["slots_full"]:
        parts = next_goal.get("components") or []
        if parts:
            parts_text = " + ".join(_display_item_name(part) for part in parts)
            detail = f"必要素材: {parts_text} / 持たせ先: {name}"
        else:
            detail = f"持たせ先: {name} / 目標: {ideal_text}"
        return {
            "priority": "high" if primary else "medium",
            "action": f"素材: {next_goal['item']}を狙う",
            "detail": detail,
        }

    if primary and target["slots_full"] and target["missing_items"]:
        return {
            "priority": "medium",
            "action": "素材: 前衛か副キャリーへ回す",
            "detail": f"{name}は3枠埋まり済み。現在: {current_text}",
        }

    return None


def _build_target_item_summary(target: Dict[str, Any], *, primary: bool) -> str:
    if not target:
        return ""

    name = target["name"]
    equipped = target["equipped_items"]
    current_text = _format_item_list(equipped) if equipped else "未装備"

    if primary and target["location"] == "bench":
        return f"{name}はベンチ。盤面に出して主キャリー化。現在: {current_text}。"
    if primary and target["location"] == "missing":
        ideal_text = _format_item_list(target["ideal_items"])
        return f"{name}は未所持。見つけたら即確保。理想装備は {ideal_text}。"
    if target["ready_to_equip"]:
        item = target["ready_to_equip"][0]
        return f"{name}は現在 {current_text}。手持ちの{item}をそのまま載せる。"
    if target["craftable_now"] and not target["slots_full"]:
        craft = target["craftable_now"][0]
        parts_text = " + ".join(_display_item_name(part) for part in craft["components"])
        return f"{name}は現在 {current_text}。今は{parts_text}から{craft['item']}を作る。"

    next_goal = target["next_goal"]
    if next_goal and target["missing_items"] and not target["slots_full"]:
        if next_goal.get("components"):
            parts_text = " + ".join(_display_item_name(part) for part in next_goal["components"])
            return f"{name}は現在 {current_text}。次は{next_goal['item']}狙い。必要素材: {parts_text}。"
        return f"{name}は現在 {current_text}。次は{next_goal['item']}を優先。"

    if primary and not target["missing_items"]:
        return f"{name}の主力装備は完成。現在: {current_text}。"
    if target["slots_full"] and target["missing_items"]:
        return f"{name}は現在 {current_text}。3枠が埋まっているので、残り素材は別ユニットへ回す。"

    return f"{name}は現在 {current_text}。"


def build_item_plan_summary(state: Any, comp_id: str) -> str:
    context = build_item_advice_context(state, comp_id)
    if not context:
        return ""

    parts: List[str] = []
    carry = context.get("carry")
    tank = context.get("tank")

    carry_summary = _build_target_item_summary(carry, primary=True) if carry else ""
    if carry_summary:
        parts.append(carry_summary)

    if tank and tank.get("name") != (carry or {}).get("name"):
        if not carry or (carry.get("slots_full") or not carry.get("missing_items")):
            tank_summary = _build_target_item_summary(tank, primary=False)
            if tank_summary:
                parts.append(tank_summary)

    if not parts and context.get("held_components"):
        held_text = _format_item_list(list(context["held_components"].elements()))
        parts.append(f"手持ち素材は {held_text}。主キャリー優先で温存。")

    return " ".join(parts[:2]).strip()


def _load_augments() -> List[dict]:
    try:
        with open(_AUGMENTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_comp_data(comp_id: str) -> Optional[dict]:
    try:
        with open(_COMPS_PATH, encoding="utf-8") as f:
            comps = json.load(f)
        return next((c for c in comps if c["id"] == comp_id), None)
    except Exception:
        return None


def _aug_tier_score(tier: str) -> int:
    return {"Prismatic": 30, "プリズマティック": 30,
            "Gold": 15, "ゴールド": 15,
            "Silver": 0, "シルバー": 0}.get(tier, 0)


def _is_augment_round(stage: str) -> bool:
    try:
        major, minor = stage.split("-")
        return (int(major), int(minor)) in {(2, 1), (3, 2), (4, 2)}
    except Exception:
        return False

def _is_gods_round(stage: str) -> bool:
    try:
        major, minor = stage.split("-")
        return (int(major), int(minor)) in {(2, 4), (3, 4), (4, 4)}
    except Exception:
        return False

def _is_god_boon_round(stage: str) -> bool:
    try:
        major, minor = stage.split("-")
        return (int(major), int(minor)) == (4, 7)
    except Exception:
        return False


# ---- Set17: 神データ（Realm of the Gods）----
GODS_DATA: Dict[str, dict] = {
    "アーリ": {
        "en": "Ahri",
        "traits": ["Fast Level", "Fast Roll", "経済", "Gold", "XP", "経験値", "リロール", "Fast 9"],
        "desc": "ゴールド・XP・リロール型。Fast Level/Rollすべての戦略に対応。経済重視の汎用神。",
        "boon": "経済オファリング（ゴールド・XP・リロール）",
        "hp_sensitive": False,
    },
    "オーレリオン・ソル": {
        "en": "Aurelion Sol",
        "traits": ["Mecha", "メカ", "Anima", "アニマ", "Primordians", "プリモーディアン", "クエスト"],
        "desc": "クエスト報酬型。AP+AD・アイテム・トレイト+1などクエスト達成で強力な報酬。メカ/アニマ構成と相性◎",
        "boon": "クエスト達成報酬（AP/AD強化・アイテム・トレイト+1）",
        "hp_sensitive": False,
    },
    "エコー": {
        "en": "Ekko",
        "traits": ["LooseStreak", "負けストリーク", "Anima", "アニマ", "スケール", "Scaling"],
        "desc": "スケーリング報酬型。数ラウンド後に効果発動。負けストリーク/後半スケール戦略と相性◎",
        "boon": "遅延スケーリング報酬（複数ラウンド後に発動）",
        "hp_sensitive": False,
    },
    "イブリン": {
        "en": "Evelynn",
        "traits": ["WinStreak", "連勝", "Rogue", "ローグ", "Assassin", "アサシン", "バースト"],
        "desc": "ハイリスク・ハイリターン型。HP消費で高価値報酬（ゴールド・チャンピオンアップグレード・エンブレム）。連勝中のみ推奨。",
        "boon": "HP消費型高価値報酬（金・アップグレード・エンブレム）",
        "hp_sensitive": True,  # HP高い時のみ有効
    },
    "ケイル": {
        "en": "Kayle",
        "traits": ["Stargazer", "スターゲイザー", "Fast9", "後期", "Scaling", "アイテム", "コンポーネント", "BIS"],
        "desc": "コンポーネント豊富型。マルチキャリーやBISアイテム構築に最適。スターゲイザー・Fast9と相性◎",
        "boon": "コンポーネント・アイテム豊富（BISアイテム構築向け）",
        "hp_sensitive": False,
    },
    "ソラカ": {
        "en": "Soraka",
        "traits": ["Shepherd", "シェパード", "Anima", "アニマ", "LooseStreak", "負けストリーク", "回復", "HP"],
        "desc": "HP回復+ゴールド型。負けストリーク向け。各ステージでHP回復+ゴールド提供。アニマ/シェパードと相性◎",
        "boon": "HP回復＋ゴールド（負けストリーク向けキャッチアップ）",
        "hp_sensitive": False,
    },
    "スレッシュ": {
        "en": "Thresh",
        "traits": [],  # ランダム — 構成不問
        "desc": "完全ランダム型。毎ステージ異なる神の報酬を獲得。ギャンブル向け。構成の縛りなし。",
        "boon": "ランダム神のBoon（各ステージで異なる神の報酬）",
        "hp_sensitive": False,
    },
    "ヴァルス": {
        "en": "Varus",
        "traits": ["Reroll", "リロール", "Dark Star", "ダークスター", "Sniper", "スナイパー", "低コスト"],
        "desc": "リロール特化型。ユニット・デュプリケーター・ゴールド提供。低コストリロール構成と相性◎",
        "boon": "ユニット＋デュプリケーター＋ゴールド（リロール向け）",
        "hp_sensitive": False,
    },
    "ヤスオ": {
        "en": "Yasuo",
        "traits": [],  # ヘックスバフ — 全構成対応
        "desc": "ヘックスバフ型。トレイト別に異なるバフヘックス（Socialite=Mana再生、Wind=攻撃速度等）。ほぼ全構成対応。",
        "boon": "トレイト固有ヘックスバフ（Mana再生・攻撃速度等）",
        "hp_sensitive": False,
    },
    "ペング": {
        "en": "Pengu",
        "traits": [],
        "desc": "HP依存の汎用報酬。順位が低いほど良いオファリング。HP30以下で特に強力。コンポーネント付き。",
        "boon": "HP依存汎用報酬（全オファリングにコンポーネント付き）",
        "hp_sensitive": True,  # HP低い時に強い
    },
}

# God Boon カテゴリ → 評価キーワード
BOON_KEYWORDS: Dict[str, List[str]] = {
    "Combat":   ["強化", "攻撃", "戦闘", "ダメージ", "combat", "attack", "power", "offensive", "AD", "AP"],
    "Economy":  ["ゴールド", "経済", "インタレスト", "Gold", "Economy", "interest", "ゴールド生成"],
    "Utility":  ["経験値", "レベル", "XP", "exp", "level", "ユーティリティ", "utility", "ヘックス"],
    "Healing":  ["回復", "HP", "ヒール", "heal", "shield", "シールド", "タクティシャン"],
    "Items":    ["アイテム", "素材", "コンポーネント", "item", "component", "forge", "デュプリケーター"],
}


# ---- Public API ----

def calc_augment_choice(choices: List[str], comp_id: str = "", stage: str = "1-1") -> dict:
    """
    3択オーグメントのうちどれを選ぶか。
    Returns {"recommended": str, "ranked": [{"name","score","reason"}]}
    """
    aug_db = {a["name"]: a for a in _load_augments()}
    comp = _load_comp_data(comp_id)
    aug_keywords: List[str] = comp.get("augment_keywords", []) if comp else []

    economy_kw = ["経済", "Gold", "Economy", "後期", "Fast 9", "リロール",
                  "スプーン", "パンドラ", "大勝利", "忍耐", "ローリング"]

    # 2-1 は経済ボーナス高め
    try:
        major, minor = stage.split("-")
        eco_weight = 1.5 if int(major) <= 2 else 1.0
    except Exception:
        eco_weight = 1.0

    ranked = []
    for choice in choices:
        aug_info = aug_db.get(choice, {})
        tier = aug_info.get("tier", "Silver")
        keywords = aug_info.get("keywords", [])
        desc = aug_info.get("desc", "")

        score = _aug_tier_score(tier)
        reasons = []

        kw_match = sum(
            1 for k in aug_keywords
            if any(k.lower() in kw.lower() or kw.lower() in k.lower() for kw in keywords)
        )
        if kw_match:
            score += kw_match * 20
            reasons.append("構成シナジー◎")

        eco_match = any(
            ek.lower() in kw.lower() or kw.lower() in ek.lower()
            for ek in economy_kw for kw in keywords
        )
        if eco_match:
            score += int(15 * eco_weight)
            reasons.append("経済オーグメント" + ("（序盤特にGood）" if eco_weight > 1 else ""))

        tier_ja = {"Silver": "シルバー", "Gold": "ゴールド",
                   "Prismatic": "プリズマティック"}.get(tier, tier)
        reasons.append(tier_ja)
        if desc:
            reasons.append(desc[:35])

        ranked.append({"name": choice, "score": score, "reason": " / ".join(reasons)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (choices[0] if choices else ""),
        "ranked": ranked,
    }


def calc_forge_choice(choices: List[str], held_items: List[str] = None, comp_id: str = "") -> dict:
    """
    フォージで提示されたコンポーネントのうちどれを取るか。
    Returns {"recommended": str, "ranked": [{"name","score","reason","builds"}]}
    """
    comp = _load_comp_data(comp_id)
    item_kw: List[str] = comp.get("item_keywords", []) if comp else []

    held_norm = [_normalize(h) for h in (held_items or [])]

    ranked = []
    for raw_name in choices:
        norm = _normalize(raw_name)
        display = COMPONENT_DISPLAY.get(norm, raw_name)
        score = 0
        reasons: List[str] = []
        builds: List[str] = []

        # コンポーネント自体のキーワードマッチ
        direct = sum(1 for k in item_kw
                     if k.lower() in norm.lower() or norm.lower() in k.lower()
                     or k.lower() in raw_name.lower())
        if direct:
            score += direct * 8
            reasons.append("構成素材")

        # 保有素材との組み合わせ → 完成アイテム評価
        partners = held_norm if held_norm else [norm]
        for partner in partners:
            key = frozenset([norm, partner])
            full = COMBOS.get(key)
            if full:
                builds.append(full)
                tags = ITEM_TAGS.get(full, [])
                m = sum(1 for k in item_kw
                        if any(k.lower() in t.lower() or t.lower() in k.lower() for t in tags))
                if m:
                    score += m * 15
                    reasons.append(f"→ {full}")

        if score == 0:
            reasons.append("構成に直接関係なし")

        ranked.append({
            "name": display,
            "score": score,
            "reason": " / ".join(dict.fromkeys(reasons)) if reasons else "汎用素材",
            "builds": list(dict.fromkeys(builds)),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (choices[0] if choices else ""),
        "ranked": ranked,
    }


# ---- 状況アドバイス ----

def calc_situation_actions(state, comp_id: str = "", board_strength: Optional[int] = None) -> List[dict]:
    """
    現在の状況に応じて「今やるべきこと」を優先度付きで返す。
    Returns List[{"priority": "urgent"|"high"|"medium", "action": str, "detail": str}]
    """
    actions: List[dict] = []
    stage  = getattr(state, "stage", "1-1")
    hp     = getattr(state, "hp", 100)
    gold   = getattr(state, "gold", 0)
    level  = getattr(state, "level", 1)
    streak = getattr(state, "streak", 0)
    board  = getattr(state, "board", [])
    bench  = getattr(state, "bench", [])
    items_held = getattr(state, "items", [])

    try:
        major_s, minor_s = stage.split("-")
        major, minor = int(major_s), int(minor_s)
    except Exception:
        major, minor = 1, 1

    comp       = _load_comp_data(comp_id)
    min_level  = comp.get("min_level", 7) if comp else 7
    comp_name  = comp.get("name", "") if comp else ""
    play_style = comp.get("play_style", "") if comp else ""
    board_names = {u.name for u in board} if board else set()
    bench_names = {u.name for u in bench} if bench else set()
    shop_names = {u.name for u in getattr(state, "shop", [])} if getattr(state, "shop", []) else set()
    item_context = build_item_advice_context(state, comp_id) if comp else {}
    needs_all_in = hp <= 40 and (board_strength is None or board_strength < 50)
    needs_stabilize = hp <= 55 and (board_strength is None or board_strength < 55)

    # ── 特殊ラウンド（最優先）──
    if _is_augment_round(stage):
        actions.append({
            "priority": "urgent",
            "action": f"選ぶ: オーグメント（{stage}）",
            "detail": "3択ウィンドウの推奨1位を取る。",
        })
    if _is_gods_round(stage):
        actions.append({
            "priority": "urgent",
            "action": f"選ぶ: 神のオファリング（{stage}）",
            "detail": "神選択ツールの推奨1位を取る。",
        })
    if _is_god_boon_round(stage):
        actions.append({
            "priority": "urgent",
            "action": "選ぶ: God Boon（4-7）",
            "detail": "神アラインと構成に合うBoonを取る。",
        })

    # ── 緊急: HP 低下 ──
    if hp <= 20 or needs_all_in:
        actions.append({
            "priority": "urgent",
            "action": "D: 全額ロールして即強化",
            "detail": f"HP {hp}。買う: 2つ星候補・前衛・構成コア。",
        })
    elif needs_stabilize:
        actions.append({
            "priority": "high",
            "action": "D: 20-30Gロール",
            "detail": f"HP {hp}。前衛2体と2つ星を先に作る。",
        })

    comp_units = comp.get("units", []) if comp else []
    carry_name = comp.get("carry", "") if comp else ""

    # ── レベル・ロール判断（常に1つ表示）──
    if needs_stabilize:
        actions.append({
            "priority": "medium",
            "action": "安定後: レベル/貯金に戻す",
            "detail": "勝てる盤面になったらDを止める。",
        })
    elif "Fast 9" in play_style or "fast9" in comp_id:
        if level < 9:
            if hp <= 40:
                actions.append({
                    "priority": "high",
                    "action": "安定後: 50G維持でLv9へ",
                    "detail": "まずHPを守る。勝てる盤面になったらDを止めてEに回す。",
                })
            else:
                actions.append({
                    "priority": "high",
                    "action": "E: 50G維持でLv9へ",
                    "detail": "Dは押さない。余りゴールドを経験値に回す。",
                })
        else:
            actions.append({
                "priority": "high",
                "action": "D: Lv9で高コストを探す",
                "detail": "4・5コストを引いて完成盤面に寄せる。",
            })
    elif "リロール" in play_style:
        if level < min_level:
            actions.append({
                "priority": "high",
                "action": f"E: Lv{min_level}まで上げる",
                "detail": f"あと{max(0, min_level - level)}レベル。到達後にDで3つ星を狙う。",
            })
        elif gold >= 50:
            actions.append({
                "priority": "high",
                "action": "D: 50G維持でスローリロール",
                "detail": "毎ラウンド余剰分だけ回して3つ星を狙う。",
            })
        elif hp <= 40:
            actions.append({
                "priority": "high",
                "action": "D: 30Gまでロール",
                "detail": "HPが低いので利子より盤面を優先。",
            })
        else:
            actions.append({
                "priority": "high",
                "action": "貯金: 50Gまで待つ",
                "detail": "50G到達後にスローリロールへ入る。",
            })
    else:
        if level < min_level:
            actions.append({
                "priority": "high",
                "action": f"E: Lv{min_level}へ上げる",
                "detail": f"{comp_name or '狙う構成'}はLv{min_level}から完成を狙う。",
            })
        elif major >= 3:
            actions.append({
                "priority": "high",
                "action": f"D: Lv{level}で20-30Gロール",
                "detail": f"{comp_name or '狙う構成'}のコアを揃えたら止める。",
            })
        else:
            early = comp.get("early_board", []) if comp else []
            missing_early = [u for u in early if u not in board_names][:3]
            if missing_early:
                actions.append({
                    "priority": "medium",
                    "action": f"買う: {'・'.join(missing_early)}",
                    "detail": "序盤ボード用。Dは押さずショップで見えたら買う。",
                })
            else:
                actions.append({
                    "priority": "medium",
                    "action": "貯金: 10/20/30Gの利子を作る",
                    "detail": "序盤盤面は足りている。Dは押さない。",
                })

    carry_item_action = _build_target_item_action(item_context.get("carry", {}), primary=True)
    if carry_item_action:
        actions.append(carry_item_action)

    tank_item_action = _build_target_item_action(item_context.get("tank", {}), primary=False)
    carry_state = item_context.get("carry", {})
    if tank_item_action and (
        not carry_state
        or carry_state.get("slots_full")
        or not carry_state.get("missing_items")
    ):
        actions.append(tank_item_action)

    # ── 買う/探す駒 ──
    key_units = [u["name"] for u in comp_units if u.get("stars", 2) >= 2]
    shop_targets = [u for u in key_units if u in shop_names and u not in board_names][:3]
    bench_targets = [u for u in key_units if u in bench_names and u not in board_names][:3]
    missing_keys = [u for u in key_units if u not in board_names][:3]

    if shop_targets:
        actions.append({
            "priority": "high",
            "action": f"買う: {'・'.join(shop_targets)}",
            "detail": f"{comp_name or '狙う構成'}のコア。見えているうちに購入。",
        })
    elif bench_targets:
        actions.append({
            "priority": "high",
            "action": f"出す: {'・'.join(bench_targets)}",
            "detail": "ベンチのコア駒を盤面に反映する。",
        })
    elif missing_keys:
        actions.append({
            "priority": "high",
            "action": f"探す: {'・'.join(missing_keys)}",
            "detail": "ショップに出たら買う。D中はこの駒を優先。",
        })

    # ── 盤面配置: 今レベルで何を出してどこに置くか ──
    if comp_units:
        ideal = comp_units[:level]
        front_board = [u["name"] for u in ideal if u.get("position") == "frontline"]
        back_board  = [u["name"] for u in ideal if u.get("position") != "frontline"]

        if not front_board:
            all_fl = [u["name"] for u in comp_units if u.get("position") == "frontline"]
            if all_fl:
                front_board = [all_fl[0]]
                back_board = back_board[:-1] if back_board else back_board

        bench_now = [u["name"] for u in comp_units[level:level + 2]]

        parts = []
        if back_board:
            parts.append(f"後列: {'・'.join(back_board)}")
        if front_board:
            parts.append(f"前列: {'・'.join(front_board)}")

        detail_carry = f"{carry_name}を後列右端〜中央に固定。" if carry_name else ""
        detail_bench = f"ベンチ待機: {'・'.join(bench_now)}" if bench_now else ""

        actions.append({
            "priority": "medium",
            "action": f"置く: {' / '.join(parts)}",
            "detail": " ".join(part for part in [detail_carry, detail_bench] if part),
        })

    # ── 連勝/連敗ストリーク維持 ──
    if streak >= 3:
        actions.append({
            "priority": "medium",
            "action": f"維持: {streak}連勝盤面を崩さない",
            "detail": "不要な売却・ロールはしない。",
        })
    elif streak <= -3:
        actions.append({
            "priority": "medium",
            "action": f"維持: {abs(streak)}連敗ボーナス",
            "detail": "HPに余裕があるなら無理に勝ちに行かない。",
        })

    # ── アイテム未装備 ──
    if len(items_held) >= 2 and not carry_item_action and not tank_item_action:
        actions.append({
            "priority": "medium",
            "action": f"作る: 素材{len(items_held)}個を消化",
            "detail": "キャリー用完成品を作る。迷うなら金床ツールを見る。",
        })

    # ── 優先度ソート・重複除去 ──
    priority_order = {"urgent": 0, "high": 1, "medium": 2}
    actions.sort(key=lambda x: priority_order.get(x["priority"], 3))

    deduped: List[dict] = []
    seen_actions: set[str] = set()
    for action in actions:
        key = action.get("action", "")
        if key in seen_actions:
            continue
        seen_actions.add(key)
        deduped.append(action)

    return deduped[:5]


def calc_gods_choice(
    gods_offered: List[str],
    comp_id: str = "",
    god_align: str = "",
    hp: int = 100,
) -> dict:
    """
    Realm of the Gods で提示された神のうちどれを選ぶか。
    Returns {"recommended": str, "ranked": [{"name","score","reason"}]}
    """
    comp = _load_comp_data(comp_id)
    comp_affinities: List[str] = comp.get("god_affinities", []) if comp else []
    comp_tags: List[str] = (comp.get("key_tags", []) + comp.get("traits", [])) if comp else []
    play_style: str = comp.get("play_style", "") if comp else ""

    # Pengu は常に候補に加える
    candidates = list(gods_offered)
    if "ペング" not in candidates:
        candidates.append("ペング")

    ranked = []
    for god_name in candidates:
        god = GODS_DATA.get(god_name)
        if not god:
            ranked.append({"name": god_name, "score": 0, "reason": "不明な神"})
            continue

        score = 0
        reasons: List[str] = []

        # 構成アフィニティの直接マッチ
        if god_name in comp_affinities:
            score += 40
            reasons.append("構成との相性◎")

        # traitキーワードマッチ
        trait_match = sum(
            1 for t in god.get("traits", [])
            if any(t.lower() in ct.lower() or ct.lower() in t.lower() for ct in comp_tags + [play_style])
        )
        if trait_match:
            score += trait_match * 15
            reasons.append(f"トレイト一致({trait_match})")

        # 神アライン継続ボーナス
        if god_align and god_name == god_align:
            score += 25
            reasons.append("アライン継続ボーナス")

        # HP依存スコア
        if god.get("hp_sensitive"):
            if god_name == "ペング":
                # ペングはHP低いほど強い
                pengu_bonus = max(0, (60 - hp) // 2)
                if hp <= 30:
                    score += 30 + pengu_bonus
                    reasons.append(f"HP{hp}でペング強力")
                elif hp <= 50:
                    score += 15 + pengu_bonus
                    reasons.append(f"HP{hp}でペング有効")
            elif god_name == "イブリン":
                # イブリンはHP高いほど安全
                if hp >= 70:
                    score += 20
                    reasons.append("HP十分でリスク許容")
                else:
                    score -= 10
                    reasons.append(f"HP{hp}でリスク高（HP消費）")

        # ベーススコア
        if not reasons:
            score += 5
            reasons.append("汎用オファリング")

        reasons.append(god.get("desc", "")[:35])
        ranked.append({"name": god_name, "score": max(0, score), "reason": " / ".join(reasons)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (candidates[0] if candidates else ""),
        "ranked": ranked,
    }


def calc_god_boon(
    boons_offered: List[str],
    comp_id: str = "",
    god_align: str = "",
) -> dict:
    """
    God Boon（ステージ4-7）の選択アドバイス。
    Returns {"recommended": str, "ranked": [{"name","score","reason"}]}
    """
    comp = _load_comp_data(comp_id)
    comp_tags: List[str] = (
        comp.get("key_tags", []) + comp.get("traits", []) + comp.get("item_keywords", [])
    ) if comp else []
    play_style: str = comp.get("play_style", "") if comp else ""

    # アライン神のBoon傾向
    aligned_god = GODS_DATA.get(god_align, {})
    aligned_boon_hint: str = aligned_god.get("boon", "")

    ranked = []
    for boon in boons_offered:
        score = 0
        reasons: List[str] = []
        boon_lower = boon.lower()

        # アライン神のBoonヒントとのマッチ
        if aligned_boon_hint and any(w in boon_lower for w in aligned_boon_hint.lower().split("（")[0].split("・")):
            score += 30
            reasons.append(f"アライン神({god_align})のBoon")

        # カテゴリキーワードマッチ
        for cat, kws in BOON_KEYWORDS.items():
            m = sum(1 for kw in kws if kw.lower() in boon_lower)
            if m:
                score += m * 10

                # 構成との相性
                comp_match = sum(
                    1 for ct in comp_tags
                    if any(kw.lower() in ct.lower() or ct.lower() in kw.lower() for kw in kws)
                )
                if comp_match:
                    score += comp_match * 8
                    reasons.append(f"{cat}ボーン(構成マッチ)")
                else:
                    reasons.append(f"{cat}ボーン")

        # Fast9/リロールの経済Boon優遇
        eco_kws = ["Gold", "ゴールド", "経済", "XP", "経験値"]
        if any(ek in play_style for ek in ["Fast 9", "リロール"]):
            if any(ek.lower() in boon_lower for ek in eco_kws):
                score += 15
                reasons.append("戦略との経済シナジー")

        if not reasons:
            score = 5
            reasons.append("汎用Boon")

        ranked.append({"name": boon, "score": score, "reason": " / ".join(dict.fromkeys(reasons))})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (boons_offered[0] if boons_offered else ""),
        "ranked": ranked,
    }
