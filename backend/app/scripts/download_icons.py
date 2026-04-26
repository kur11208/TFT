"""
Download TFT champion portrait icons from Data Dragon (TFT set-specific splash art).

Usage:
    cd backend
    python -m app.scripts.download_icons
"""
import json
import os
import sys

import requests

_ICONS_DIR = os.path.join(os.path.dirname(__file__), "../data/champion_icons")
_MAPPING_OUT = os.path.join(_ICONS_DIR, "mapping.json")

# champions.json の名前 → TFT17 Data Dragon の日本語名（表記ズレ対応）
_NAME_OVERRIDE: dict[str, str] = {
    "アートロックス":           "エイトロックス",
    "ブライア":                 "ブライアー",
    "イズリール":               "エズリアル",
    "トゥイステッド・フェイト": "ツイステッド・フェイト",
    "グナー":                   "ナー",
    "ミープシー":               "ミィプシー",
    "ヌヌ":                     "ヌヌ & ウィルンプ",
    "リヴン":                   "リヴェン",
    "アウレリオン・ソル":       "オレリオン・ソル",
}


def get_latest_version() -> str:
    r = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=10)
    r.raise_for_status()
    return r.json()[0]


def fetch_tft_champions(version: str) -> dict[str, str]:
    """Return {jp_name: image_filename} for the latest TFT set."""
    r = requests.get(
        f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ja_JP/tft-champion.json",
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()["data"]

    # 最新セット番号を自動検出（最大の TFTxx_ プレフィックス）
    set_nums = set()
    for v in data.values():
        fname = v["image"]["full"]
        if fname.startswith("TFT") and "_" in fname:
            try:
                set_nums.add(int(fname[3:fname.index("_")]))
            except ValueError:
                pass
    latest_set = max(set_nums) if set_nums else 17
    prefix = f"TFT{latest_set}_"
    print(f"Detected TFT set: {latest_set}")

    result: dict[str, str] = {}
    for v in data.values():
        fname = v["image"]["full"]
        if fname.startswith(prefix):
            result[v["name"]] = fname
    return result


def download_icons(version: str, champ_names: list[str]) -> dict[str, str]:
    """
    Download TFT splash portraits for each champion in champ_names.
    Returns {champ_name_in_champions_json: saved_filename} mapping.
    """
    os.makedirs(_ICONS_DIR, exist_ok=True)
    tft_map = fetch_tft_champions(version)
    base_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/tft-champion"

    mapping: dict[str, str] = {}
    ok = err = skip = 0

    for jp in champ_names:
        lookup = _NAME_OVERRIDE.get(jp, jp)
        fname = tft_map.get(lookup)
        if not fname:
            print(f"  skip (not in TFT set) {jp} (tried '{lookup}')")
            skip += 1
            continue

        path = os.path.join(_ICONS_DIR, fname)
        if os.path.exists(path):
            mapping[jp] = fname
            ok += 1
            print(f"  skip (exists) {jp} → {fname}")
            continue

        url = f"{base_url}/{fname}"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(resp.content)
            mapping[jp] = fname
            ok += 1
            print(f"  OK  {jp} → {fname}")
        except Exception as e:
            err += 1
            print(f"  ERR {jp}: {e}")

    print(f"\nDone: {ok} OK, {err} errors, {skip} skipped")
    return mapping


def load_champion_names() -> list[str]:
    champs_path = os.path.join(_ICONS_DIR, "../current/champions.json")
    with open(champs_path, "r", encoding="utf-8") as f:
        return [c["name"] for c in json.load(f)]


def main():
    print("Fetching latest Data Dragon version...")
    try:
        version = get_latest_version()
    except Exception as e:
        print(f"Failed to fetch version: {e}")
        sys.exit(1)
    print(f"Version: {version}\n")

    champ_names = load_champion_names()
    print(f"Champions in champions.json: {len(champ_names)}\n")

    mapping = download_icons(version, champ_names)

    with open(_MAPPING_OUT, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    print(f"\nMapping saved → {_MAPPING_OUT}")
    print(f"Total icons mapped: {len(mapping)}")


if __name__ == "__main__":
    main()
