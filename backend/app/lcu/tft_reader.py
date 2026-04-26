import json
import os
import requests
import urllib3
from datetime import datetime
from typing import Dict, Any, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LOG_PATH = os.path.join(os.path.dirname(__file__), "../../logs/api_debug.jsonl")


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
        def _extract_item_names(obj) -> list:
            names = []
            for key in ('items', 'tftItems', 'heldItems', 'inventoryItems'):
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
            return names

        item_names = _extract_item_names(active)
        if not item_names:
            local_name = active.get('summonerName') or active.get('riotId') or ''
            if local_name:
                player = _find_local_player(live, local_name)
                if player:
                    item_names = _extract_item_names(player)
                    # allPlayers の units からアイテムを集める
                    if not item_names:
                        for unit in (player.get('units') or player.get('champions') or []):
                            if isinstance(unit, dict):
                                item_names.extend(_extract_item_names(unit))
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
