import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

from ..logic.item_advisor import COMPONENT_DISPLAY, GODS_DATA, canonicalize_item_name

_DATA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
_AUGMENT_MAPPING_PATH = os.path.join(_DATA_ROOT, "augment_icons", "mapping.json")
_AUGMENTS_PATH = os.path.join(_DATA_ROOT, "current", "augments.json")
_ITEMS_PATH = os.path.join(_DATA_ROOT, "current", "items.json")

_COMMON_FIXES = {
    "ボータブル": "ポータブル",
    "バック": "バッグ",
    "麻法": "魔法",
    "廃法": "魔法",
    "央雄": "英雄",
    "貞雄": "英雄",
    "和議": "英雄",
    "共のラッキーバッグ": "英雄のラッキーバッグ",
    "ィプリン": "イブリン",
    "イプリン": "イブリン",
    "ィフリン": "イブリン",
}


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "").strip())
    for source, replacement in _COMMON_FIXES.items():
        text = text.replace(source, replacement)
    text = re.sub(r"[|/\\\\_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _search_key(value: str) -> str:
    key = re.sub(r"[\W_]+", "", _normalize_text(value))
    for source, replacement in _COMMON_FIXES.items():
        source_key = re.sub(r"[\W_]+", "", source)
        replacement_key = re.sub(r"[\W_]+", "", replacement)
        if source_key:
            key = key.replace(source_key, replacement_key)
    return key


def _partial_ratio(text: str, target: str) -> float:
    if not text or not target:
        return 0.0
    if target in text or text in target:
        return min(len(text), len(target)) / max(len(text), len(target))

    best = SequenceMatcher(None, text, target).ratio()
    if len(text) <= len(target):
        return best

    width = len(target)
    for start in range(0, len(text) - width + 1):
        window = text[start:start + width]
        best = max(best, SequenceMatcher(None, window, target).ratio())
    return best


def _resolve(raw_text: str, aliases: list[tuple[str, str]], min_ratio: float) -> str:
    raw_key = _search_key(raw_text)
    if not raw_key:
        return ""

    exact_matches = [canonical for alias_key, canonical in aliases if alias_key == raw_key]
    if exact_matches:
        return min(exact_matches, key=len)

    contains_matches = [
        canonical
        for alias_key, canonical in aliases
        if alias_key in raw_key or raw_key in alias_key
    ]
    if contains_matches:
        return min(contains_matches, key=len)

    best_name = ""
    best_ratio = 0.0
    for alias_key, canonical in aliases:
        ratio = _partial_ratio(raw_key, alias_key)
        if ratio > best_ratio:
            best_ratio = ratio
            best_name = canonical

    return best_name if best_ratio >= min_ratio else ""


@lru_cache(maxsize=1)
def _augment_aliases() -> list[tuple[str, str]]:
    names: set[str] = set()

    if os.path.exists(_AUGMENT_MAPPING_PATH):
        with open(_AUGMENT_MAPPING_PATH, "r", encoding="utf-8") as handle:
            names.update(str(name).strip() for name in json.load(handle).keys())

    if os.path.exists(_AUGMENTS_PATH):
        with open(_AUGMENTS_PATH, "r", encoding="utf-8") as handle:
            for row in json.load(handle):
                name = str((row or {}).get("name") or "").strip()
                if name:
                    names.add(name)

    return [(_search_key(name), name) for name in sorted(names, key=len, reverse=True) if _search_key(name)]


@lru_cache(maxsize=1)
def _god_aliases() -> list[tuple[str, str]]:
    return [(_search_key(name), name) for name in GODS_DATA.keys() if _search_key(name)]


@lru_cache(maxsize=1)
def _component_aliases() -> list[tuple[str, str]]:
    aliases: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    if os.path.exists(_ITEMS_PATH):
        with open(_ITEMS_PATH, "r", encoding="utf-8") as handle:
            for row in json.load(handle):
                if not (row or {}).get("component"):
                    continue
                canonical = str(row.get("name") or "").strip()
                if not canonical:
                    continue
                for alias in (row.get("name"), row.get("short"), row.get("en")):
                    key = _search_key(str(alias or ""))
                    pair = (key, canonical)
                    if key and pair not in seen:
                        seen.add(pair)
                        aliases.append(pair)

    for display in COMPONENT_DISPLAY.values():
        key = _search_key(display)
        pair = (key, display)
        if key and pair not in seen:
            seen.add(pair)
            aliases.append(pair)

    return aliases


def resolve_augment_name(raw_text: str) -> str:
    return _resolve(raw_text, _augment_aliases(), min_ratio=0.58)


def resolve_god_name(raw_text: str) -> str:
    return _resolve(raw_text, _god_aliases(), min_ratio=0.52)


def resolve_component_name(raw_text: str) -> str:
    resolved = _resolve(raw_text, _component_aliases(), min_ratio=0.5)
    if resolved:
        return resolved

    canonical = canonicalize_item_name(_normalize_text(raw_text))
    return COMPONENT_DISPLAY.get(canonical, "")
