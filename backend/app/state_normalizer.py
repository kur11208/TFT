from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any, Iterable, Optional

from .schemas import AnalyzeRequest, Unit

_CHAMPIONS_PATH = os.path.join(os.path.dirname(__file__), "data/current/champions.json")
_CHAMPION_ICON_MAPPING_PATH = os.path.join(os.path.dirname(__file__), "data/champion_icons/mapping.json")
_STAGE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")
_CHAMPION_NAME_ALIASES = {
    "エイトロックス": "アートロックス",
    "エズリアル": "イズリール",
    "オレリオン・ソル": "アウレリオン・ソル",
    "ツイステッド・フェイト": "トゥイステッド・フェイト",
    "ナー": "グナー",
    "ヌヌ & ウィルンプ": "ヌヌ",
    "ブライアー": "ブライア",
    "ミィプシー": "ミープシー",
    "リヴェン": "リヴン",
}


def _clean_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


@lru_cache(maxsize=1)
def _load_champions() -> list[dict[str, Any]]:
    try:
        with open(_CHAMPIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


@lru_cache(maxsize=1)
def _champion_lookup() -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for champ in _load_champions():
        name = str(champ.get("name", "")).strip()
        if not name:
            continue
        lookup[name.lower()] = champ
        lookup[_clean_name(name)] = champ
    return lookup


@lru_cache(maxsize=1)
def _champion_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    try:
        with open(_CHAMPION_ICON_MAPPING_PATH, "r", encoding="utf-8") as f:
            mapping = json.load(f)
    except Exception:
        return aliases

    if not isinstance(mapping, dict):
        return aliases

    for localized_name, filename in mapping.items():
        if not isinstance(localized_name, str) or not isinstance(filename, str):
            continue
        match = re.search(r"TFT\d+_([A-Za-z]+)", filename)
        if not match:
            continue
        aliases[_clean_name(match.group(1))] = localized_name
    return aliases


def _coerce_int(value: Any, minimum: Optional[int] = None, maximum: Optional[int] = None) -> Optional[int]:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        return None

    if minimum is not None and parsed < minimum:
        return None
    if maximum is not None and parsed > maximum:
        return None
    return parsed


def _normalize_stage(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        for key in ("round", "stage", "value"):
            nested = _normalize_stage(value.get(key))
            if nested:
                return nested
        return None

    if value is None:
        return None

    text = str(value).strip()
    match = _STAGE_RE.search(text)
    if not match:
        return None

    major = int(match.group(1))
    minor = int(match.group(2))
    if not (1 <= major <= 9 and 1 <= minor <= 7):
        return None
    return f"{major}-{minor}"


def _iter_collection(value: Any) -> Iterable[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in (
            "units",
            "slots",
            "items",
            "cards",
            "shop",
            "bench",
            "board",
            "shop_pieces",
            "bench_pieces",
            "board_pieces",
        ):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
            if isinstance(nested, dict):
                return [entry for entry in nested.values() if isinstance(entry, (dict, list, str))]
        return [nested for nested in value.values() if isinstance(nested, (dict, list, str))]
    return []


def _candidate_name(value: Any) -> Optional[str]:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if not isinstance(value, dict):
        return None

    for key in (
        "name",
        "displayName",
        "display_name",
        "championName",
        "champion_name",
        "character",
        "characterName",
        "unit",
        "title",
        "id",
    ):
        nested = value.get(key)
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _resolve_champion(raw_name: Any) -> Optional[dict[str, Any]]:
    candidate = _candidate_name(raw_name)
    if not candidate:
        return None

    lookup = _champion_lookup()
    alias_candidate = _CHAMPION_NAME_ALIASES.get(candidate, candidate)
    direct = lookup.get(candidate.lower()) or lookup.get(_clean_name(candidate))
    if direct:
        return direct
    if alias_candidate != candidate:
        direct = lookup.get(alias_candidate.lower()) or lookup.get(_clean_name(alias_candidate))
        if direct:
            return direct

    alias_name = _champion_aliases().get(_clean_name(candidate))
    if alias_name:
        direct = lookup.get(alias_name.lower()) or lookup.get(_clean_name(alias_name))
        if direct:
            return direct

    cleaned = _clean_name(candidate)
    if cleaned.startswith("tft") and "_" in candidate:
        suffix = candidate.split("_")[-1]
        direct = lookup.get(suffix.lower()) or lookup.get(_clean_name(suffix))
        if direct:
            return direct
        alias_name = _champion_aliases().get(_clean_name(suffix))
        if alias_name:
            direct = lookup.get(alias_name.lower()) or lookup.get(_clean_name(alias_name))
            if direct:
                return direct

    best_match: Optional[dict[str, Any]] = None
    best_score = 0.0
    for champ in _load_champions():
        name = str(champ.get("name", "")).strip()
        if not name:
            continue
        score = SequenceMatcher(None, cleaned, _clean_name(name)).ratio()
        if score > best_score:
            best_score = score
            best_match = champ

    return best_match if best_score >= 0.64 else None


def _extract_stars(value: Any) -> int:
    if isinstance(value, dict):
        for key in ("stars", "star", "tier", "rank", "upgradeLevel"):
            parsed = _coerce_int(value.get(key), minimum=1, maximum=3)
            if parsed is not None:
                return parsed
    return 1


def _unit_from_external(value: Any) -> Optional[Unit]:
    champion = _resolve_champion(value)
    if not champion:
        return None

    return Unit(
        name=str(champion["name"]),
        stars=_extract_stars(value),
        tags=list(champion.get("tags", [])),
    )


def _normalize_units(value: Any) -> list[Unit]:
    units: list[Unit] = []
    seen: set[str] = set()
    for raw_unit in _iter_collection(value):
        unit = _unit_from_external(raw_unit)
        if unit is None:
            continue
        dedupe_key = f"{unit.name}:{unit.stars}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        units.append(unit)
    return units


def _normalize_names(value: Any) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for item in _iter_collection(value):
        if isinstance(item, dict):
            for key in ("name", "displayName", "display_name", "title", "id"):
                nested = item.get(key)
                if isinstance(nested, str) and nested.strip():
                    name = nested.strip()
                    break
            else:
                continue
        elif isinstance(item, str):
            name = item.strip()
        else:
            continue

        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def normalize_gep_state(raw_state: dict[str, Any] | None) -> dict[str, Any]:
    base = AnalyzeRequest().model_dump()
    if not raw_state:
        return base

    stage = _normalize_stage(raw_state.get("stage")) or _normalize_stage(raw_state.get("game_stage"))
    hp = _coerce_int(raw_state.get("hp"), minimum=0, maximum=100)
    if hp is None:
        hp = _coerce_int(raw_state.get("health"), minimum=0, maximum=100)

    level = _coerce_int(raw_state.get("level"), minimum=1, maximum=10)
    gold = _coerce_int(raw_state.get("gold"), minimum=0, maximum=999)

    base.update(
        {
            "stage": stage or base["stage"],
            "level": level if level is not None else base["level"],
            "hp": hp if hp is not None else base["hp"],
            "gold": gold if gold is not None else base["gold"],
            "board": [unit.model_dump() for unit in _normalize_units(raw_state.get("board"))],
            "bench": [unit.model_dump() for unit in _normalize_units(raw_state.get("bench"))],
            "shop": [unit.model_dump() for unit in _normalize_units(raw_state.get("shop"))],
            "items": _normalize_names(raw_state.get("items")),
            "augments": _normalize_names(raw_state.get("augments")),
        }
    )
    return base
