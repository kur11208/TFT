import json
import os
import requests
import time
import urllib3
from datetime import datetime
from typing import Dict, Any, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LOG_PATH = os.path.join(os.path.dirname(__file__), "../../logs/api_debug.jsonl")
_OCR_STAGE_CACHE: Dict[str, Any] = {"stage": None, "at": 0.0}


def _write_log(entry: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        # 1000行超えたら古い方を切り捨て
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > 1000:
            with open(_LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines[-800:])
    except Exception:
        pass

# ゲーム経過時間(秒) → ステージ推定
# TFT1ラウンド: 企画フェーズ30s + 戦闘フェーズ平均25s + 移行5s ≈ 60s
# カルーセル: 30s / PvEラウンドは短め
# 以下は実測値ベースの近似。LCU経由で stage が取れる場合はそちらを優先。
_STAGE_BREAKPOINTS = [
    (0,    '1-1'),
    (80,   '1-2'),
    (160,  '1-3'),
    (270,  '2-1'),   # カルーセル後
    (345,  '2-2'),
    (420,  '2-3'),
    (500,  '2-4'),
    (580,  '2-5'),
    (680,  '3-1'),   # カルーセル後
    (760,  '3-2'),
    (840,  '3-3'),
    (920,  '3-4'),
    (1005, '3-5'),
    (1095, '4-1'),   # カルーセル後
    (1180, '4-2'),
    (1270, '4-3'),
    (1360, '4-4'),
    (1455, '4-5'),
    (1545, '5-1'),
    (1635, '5-2'),
    (1725, '5-3'),
    (1820, '5-4'),
    (1910, '5-5'),
    (2010, '6-1'),
    (2105, '6-2'),
    (2200, '6-3'),
    (2295, '6-4'),
    (2395, '7-1'),
    (2490, '7-2'),
    (2590, '7-3'),
]


def _estimate_stage(t: float) -> str:
    stage = '1-1'
    for threshold, s in _STAGE_BREAKPOINTS:
        if t >= threshold:
            stage = s
        else:
            break
    return stage


def _extract_stage_from_live(live: Dict) -> Optional[str]:
    """
    allgamedata レスポンスから TFT ステージ文字列 (X-Y) を探す。
    Riot は複数バージョンでパスが変わるため候補を順番に試す。
    """
    import re
    _stage_re = re.compile(r'^\d+-\d+$')

    def _try(val) -> Optional[str]:
        if isinstance(val, str) and _stage_re.match(val.strip()):
            return val.strip()
        return None

    # 候補パス一覧
    candidates = [
        live.get('stage'),
        (live.get('gameData') or {}).get('stage'),
        (live.get('gameData') or {}).get('tftStage'),
        (live.get('activePlayer') or {}).get('stage'),
        (live.get('activePlayer') or {}).get('tftStage'),
        (live.get('activePlayer') or {}).get('currentStage'),
    ]
    for v in candidates:
        r = _try(v)
        if r:
            return r

    # トップレベルを総当たりで "X-Y" 形式のフィールドを探す
    for key, val in live.items():
        r = _try(val)
        if r:
            return r
        if isinstance(val, dict):
            for k2, v2 in val.items():
                r = _try(v2)
                if r:
                    return r

    return None


def _ocr_stage() -> Optional[str]:
    """画面のステージ表示をOCRで直接読む。成功すれば 'X-Y' を返す。"""
    try:
        from ..capture.screenshot import capture_region, get_screen_size
        from ..capture.regions import scale_regions_to_screen
        from ..capture.ocr import ocr_stage as ocr_stage_region

        screen_w, screen_h = get_screen_size()
        regions = scale_regions_to_screen(screen_w, screen_h)

        stage_region = regions.get("stage")
        if not stage_region:
            return None

        img = capture_region(stage_region)
        if img is None:
            return None

        stage, conf = ocr_stage_region(img)
        if conf < 0.35:
            return None

        return stage or None
    except Exception:
        return None


def _cached_ocr_stage(ttl: float = 2.0) -> Optional[str]:
    now = time.time()
    if now - float(_OCR_STAGE_CACHE.get("at") or 0.0) < ttl:
        return _OCR_STAGE_CACHE.get("stage")

    stage = _ocr_stage()
    _OCR_STAGE_CACHE["stage"] = stage
    _OCR_STAGE_CACHE["at"] = now
    return stage


def get_live_client_data() -> Optional[Dict]:
    """Port 2999 Live Client Data API (active only during a game)."""
    try:
        r = requests.get(
            'https://127.0.0.1:2999/liveclientdata/allgamedata',
            verify=False, timeout=2,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _get_active_player(live: Dict) -> Optional[Dict]:
    """Return the activePlayer node, tolerating TFT's sparse schema."""
    return live.get('activePlayer') or {}


def _find_local_player(live: Dict, summoner_name: str) -> Optional[Dict]:
    """Find local player in allPlayers list by summonerName (case-insensitive)."""
    players = live.get('allPlayers') or []
    name_lower = summoner_name.lower()
    for p in players:
        pname = (p.get('summonerName') or p.get('riotId') or '').lower()
        if pname == name_lower or pname.startswith(name_lower):
            return p
    # Fall back to first player if only one player exists (solo test)
    if len(players) == 1:
        return players[0]
    return None


def _extract_int(obj: Dict, *keys: str) -> Optional[int]:
    """Try multiple keys, return first int found."""
    for k in keys:
        v = obj.get(k)
        if v is not None:
            try:
                return int(float(v))
            except (TypeError, ValueError):
                pass
    return None


def _extract_item_names(obj: Dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ('items', 'tftItems', 'heldItems', 'inventoryItems', 'equipment', 'equippedItems', 'itemNames'):
        val = obj.get(key)
        if not isinstance(val, list):
            continue
        for item in val:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                n = item.get('displayName') or item.get('name') or item.get('id') or ''
                if n:
                    names.append(str(n))
    return list(dict.fromkeys(names))


def _classify_live_unit(unit: Dict[str, Any]) -> Optional[str]:
    if not isinstance(unit, dict):
        return None

    for key in ('benchIndex', 'benchSlot', 'benchPosition'):
        if unit.get(key) is not None:
            return 'bench'
    for key in ('boardIndex', 'boardSlot', 'cellId', 'hexCell', 'hexCellId'):
        if unit.get(key) is not None:
            return 'board'

    if unit.get('isBench') is True or unit.get('onBench') is True or unit.get('benched') is True:
        return 'bench'
    if unit.get('isBoard') is True or unit.get('onBoard') is True:
        return 'board'

    location = str(unit.get('location') or unit.get('zone') or '').strip().lower()
    if location in {'bench', 'reserve', 'hand'}:
        return 'bench'
    if location in {'board', 'field', 'battlefield'}:
        return 'board'

    if unit.get('x') is not None and unit.get('y') is not None:
        return 'board'
    return None


def _extract_live_units(player: Dict[str, Any]) -> tuple[list[dict], list[dict], list[dict]]:
    from ..state_normalizer import _unit_from_external

    board_units: list[dict] = []
    bench_units: list[dict] = []
    all_units: list[dict] = []

    for raw_unit in (player.get('units') or player.get('champions') or []):
        if not isinstance(raw_unit, dict):
            continue
        unit = _unit_from_external(raw_unit)
        if unit is None:
            continue
        normalized = unit.model_dump()
        all_units.append(normalized)
        bucket = _classify_live_unit(raw_unit)
        if bucket == 'board':
            board_units.append(normalized)
        elif bucket == 'bench':
            bench_units.append(normalized)

    return board_units, bench_units, all_units


def _merge_unit_items(existing_units: list[dict], live_units: list[dict]) -> list[dict]:
    if not existing_units or not live_units:
        return existing_units

    exact: dict[tuple[str, int], list[dict]] = {}
    fallback: dict[str, list[dict]] = {}
    for unit in live_units:
        items = unit.get('items') or []
        if not items:
            continue
        name = str(unit.get('name') or '').strip()
        stars = int(unit.get('stars') or 1)
        if not name:
            continue
        exact.setdefault((name, stars), []).append(unit)
        fallback.setdefault(name, []).append(unit)

    merged: list[dict] = []
    for unit in existing_units:
        updated = dict(unit)
        current_items = updated.get('items') or []
        name = str(updated.get('name') or '').strip()
        stars = int(updated.get('stars') or 1)
        source = None

        exact_bucket = exact.get((name, stars))
        if exact_bucket:
            source = exact_bucket.pop(0)
            fallback_bucket = fallback.get(name)
            if fallback_bucket and source in fallback_bucket:
                fallback_bucket.remove(source)
        elif fallback.get(name):
            source = fallback[name].pop(0)

        if source and source.get('items') and not current_items:
            updated['items'] = list(source['items'])
        elif current_items:
            updated['items'] = list(current_items)
        else:
            updated['items'] = []

        merged.append(updated)

    return merged


def read_tft_state(lcu_client=None, existing=None) -> Dict[str, Any]:
    """
    Combine Live Client API + LCU session to build TFT game state.
    Fields not obtainable from APIs keep their existing values.
    """
    raw: Dict[str, Any] = {}
    confidence: Dict[str, float] = {}

    base: Dict[str, Any] = {
        'patch': 'current',
        'stage': '1-1',
        'level': 1,
        'hp': 100,
        'gold': 0,
        'streak': 0,
        'board': [],
        'bench': [],
        'shop': [],
        'items': [],
        'augments': [],
        'notes': '',
    }
    if existing:
        ex = existing.dict() if hasattr(existing, 'dict') else dict(existing)
        base.update({k: v for k, v in ex.items() if v is not None})

    # --- Live Client Data API (port 2999) ---
    live = get_live_client_data()
    if live:
        game_data = live.get('gameData') or {}
        game_time = game_data.get('gameTime', 0)
        if game_time:
            raw['gameTime'] = str(round(game_time))

        # TFT stage フィールドを複数のパスで探す（最優先）
        api_stage = _extract_stage_from_live(live)
        stage_source = None
        if api_stage:
            base['stage'] = api_stage
            raw['stage_api'] = api_stage
            confidence['stage'] = 0.99
            stage_source = 'api'
        elif game_time:
            base['stage'] = _estimate_stage(float(game_time))
            confidence['stage'] = 0.55
            stage_source = 'estimate'

        # The game-time estimate drifts by round length. Prefer the visible HUD
        # stage when OCR can read it.
        ocr_stage = _cached_ocr_stage()
        if ocr_stage:
            raw['stage_ocr'] = ocr_stage
            if ocr_stage != base.get('stage'):
                base['stage'] = ocr_stage
                confidence['stage'] = 0.90
                stage_source = 'ocr'
            elif stage_source:
                stage_source = f"{stage_source}+ocr"

        _write_log({
            'ts': datetime.utcnow().isoformat(),
            'stage': base.get('stage'),
            'stage_source': stage_source,
            'game_time': game_time,
            'confidence': confidence,
            'live_snapshot': live,
        })

        active = _get_active_player(live)

        # Gold — port 2999 の currentGold は累計獲得gold（所持goldではない）ため使わない
        # TFT の所持gold は port 2999 からは取得不可

        # Level — activePlayer.level は TFT レベルとして正確
        level = _extract_int(active, 'level', 'championLevel')
        if level is not None and 1 <= level <= 10:
            base['level'] = level
            raw['level'] = str(level)
            confidence['level'] = 0.95

        # HP — port 2999 は TFT の HP を公開していない（allPlayers にも存在しない）

        # Items — try activePlayer fields first, then local player's units
        item_names = _extract_item_names(active)
        local_name = active.get('summonerName') or active.get('riotId') or ''
        player = _find_local_player(live, local_name) if local_name else None
        board_units: list[dict] = []
        bench_units: list[dict] = []
        all_units: list[dict] = []
        if player:
            board_units, bench_units, all_units = _extract_live_units(player)

            if board_units:
                if base.get('board'):
                    base['board'] = _merge_unit_items(base['board'], board_units)
                else:
                    base['board'] = board_units
            if bench_units:
                if base.get('bench'):
                    base['bench'] = _merge_unit_items(base['bench'], bench_units)
                else:
                    base['bench'] = bench_units

            if not item_names:
                item_names = _extract_item_names(player)
            if not item_names:
                for unit in all_units:
                    item_names.extend(unit.get('items') or [])
        if item_names:
            base['items'] = list(dict.fromkeys(item_names))  # 重複除去
            raw['items'] = ', '.join(item_names)
            confidence['items'] = 0.85

        # Augments — some TFT versions expose augments list
        augments_raw = active.get('augments') or active.get('tftAugments') or []
        if isinstance(augments_raw, list) and augments_raw:
            names = []
            for aug in augments_raw:
                if isinstance(aug, str):
                    names.append(aug)
                elif isinstance(aug, dict):
                    n = aug.get('displayName') or aug.get('name') or aug.get('id') or ''
                    if n:
                        names.append(n)
            if names:
                base['augments'] = names
                raw['augments'] = ', '.join(names)
                confidence['augments'] = 0.9

    # --- LCU session (fallback metadata) ---
    if lcu_client:
        try:
            session = lcu_client.game_session()
            if session:
                raw['phase'] = session.get('phase', '')
                queue_id = session.get('gameData', {}).get('queue', {}).get('id')
                if queue_id:
                    raw['queue'] = str(queue_id)
        except Exception:
            pass

    return {'state': base, 'raw': raw, 'confidence': confidence}
