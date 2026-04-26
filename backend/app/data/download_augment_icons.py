"""
TFT Set 17 augment icon downloader.
Community Dragon から取得して data/augment_icons/ に保存する。

Usage:
    cd backend
    python -m app.data.download_augment_icons
"""
import json
import os
import re
import urllib.request
import urllib.error

CDRAGON_BASE = "https://raw.communitydragon.org/latest"
EN_URL  = f"{CDRAGON_BASE}/cdragon/tft/en_us.json"
JA_URL  = f"{CDRAGON_BASE}/cdragon/tft/ja_jp.json"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "augment_icons")

AUGMENTS_JSON = os.path.join(os.path.dirname(__file__), "current", "augments.json")


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def _fetch_json(url: str) -> dict:
    print(f"  Fetching {url} ...")
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def _download_file(url: str, dest: str) -> bool:
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r, open(dest, "wb") as f:
            f.write(r.read())
        return True
    except KeyboardInterrupt:
        raise
    except Exception:
        return False


def _icon_url(raw_path: str) -> str:
    """Convert CDragon icon path to CDN URL.
    Input:  ASSETS/Maps/TFT/Icons/Augments/Hexcore/GodAugmentEkko_II.TFT_Set17.tex
    Output: https://raw.communitydragon.org/latest/game/assets/maps/tft/icons/augments/hexcore/godaugmentekko_ii.tft_set17.png
    CDragon serves .tex files as .png automatically.
    """
    p = raw_path.lower().replace("\\", "/").lstrip("/")
    # ASSETS/ → game/assets/
    if p.startswith("assets/"):
        p = "game/" + p
    elif not p.startswith("game/"):
        p = "game/assets/" + p
    # Replace texture extension with .png
    for ext in (".tex", ".dds", ".tga"):
        if p.endswith(ext):
            p = p[:-len(ext)] + ".png"
            break
    if not p.endswith((".png", ".jpg", ".jpeg", ".webp")):
        p += ".png"
    return f"{CDRAGON_BASE}/{p}"


def _collect_augments(data: dict) -> list[dict]:
    """
    Extract Set 17 augment dicts from CDragon TFT JSON.
    setData[].augments contains apiName strings; full data is in top-level items[].
    """
    # Collect Set17 augment apiNames
    set17_ids: set[str] = set()
    for set_obj in data.get("setData", []):
        if not isinstance(set_obj, dict):
            continue
        mutator = set_obj.get("mutator", "")
        if "TFTSet17" not in mutator or "PVEMODE" in mutator or "PAIRS" in mutator:
            continue
        for aug in set_obj.get("augments", []):
            if isinstance(aug, str):
                set17_ids.add(aug)
            elif isinstance(aug, dict):
                aid = aug.get("apiName", aug.get("id", ""))
                if aid:
                    set17_ids.add(aid)

    # Look up full data from top-level items list
    items = data.get("items", [])
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        aid = item.get("apiName", item.get("id", ""))
        if aid in set17_ids:
            out.append(item)
    return out


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Fetching CDragon TFT data...")
    en_data = _fetch_json(EN_URL)
    ja_data = _fetch_json(JA_URL)

    en_augs = _collect_augments(en_data)
    ja_augs = _collect_augments(ja_data)

    print(f"English augments: {len(en_augs)}")
    print(f"Japanese augments: {len(ja_augs)}")

    # Build apiName → Japanese name mapping
    ja_by_id: dict[str, str] = {}
    for aug in ja_augs:
        api_name = aug.get("apiName", "")
        name_ja = aug.get("name", "")
        if api_name and name_ja:
            ja_by_id[api_name] = name_ja

    # Load existing augments.json for cross-reference
    local_names: set[str] = set()
    if os.path.exists(AUGMENTS_JSON):
        with open(AUGMENTS_JSON, "r", encoding="utf-8") as f:
            local_names = {a["name"] for a in json.load(f)}

    mapping: dict[str, str] = {}
    skipped = 0

    for aug in en_augs:
        api_name = aug.get("apiName", aug.get("id", ""))
        name_en = aug.get("name", "")
        icon_path = (
            aug.get("icon", "")
            or aug.get("iconPath", "")
            or aug.get("image", {}).get("full", "")
        )
        if not name_en or not icon_path:
            skipped += 1
            continue

        # Prefer Japanese name; fall back to English
        name_key = ja_by_id.get(api_name, name_en)

        url = _icon_url(icon_path)
        safe = re.sub(r"[^\w\-]", "_", name_en)
        fname = f"aug_{safe}.png"
        fpath = os.path.join(OUTPUT_DIR, fname)

        if not os.path.exists(fpath):
            if not _download_file(url, fpath):
                if skipped < 3:
                    print(f"  Failed: {name_en} | URL: {url}")
                skipped += 1
                continue

        mapping[name_key] = fname

    mapping_path = os.path.join(OUTPUT_DIR, "mapping.json")
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"\nDone. {len(mapping)} icons saved, {skipped} skipped.")
    print(f"Mapping → {mapping_path}")


if __name__ == "__main__":
    main()
