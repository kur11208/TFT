"""
TFT / League of Legends プロセス監視。
LCU API を優先使用し、クライアント未起動時は psutil にフォールバック。
"""
import psutil
from typing import Optional

GAME_PROCESS_NAMES = {
    "League of Legends.exe",
    "TFTGame.exe",
    "League of Legends",
}


def find_game_via_lcu() -> Optional[str]:
    """LCU API でゲーム状態を確認（最も確実）。"""
    try:
        from .lcu.client import get_lcu_client, TFT_QUEUE_IDS
        client = get_lcu_client()
        if not client:
            return None
        session = client.game_session()
        if not session:
            return None
        phase = session.get('phase', '')
        if phase in ('InProgress', 'GameStart'):
            try:
                queue_id = int(session.get('gameData', {}).get('queue', {}).get('id', -1))
            except (TypeError, ValueError):
                queue_id = -1
            if queue_id in TFT_QUEUE_IDS:
                return f"TFT (queue={queue_id})"
            return 'League of Legends.exe'
    except Exception:
        pass
    return None


def find_game_process() -> Optional[str]:
    """psutil フォールバック: ゲームプロセス名を返す。"""
    # LCU API を先に試す
    lcu_result = find_game_via_lcu()
    if lcu_result:
        return lcu_result

    # プロセス名で検索
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"] or ""
            if name in GAME_PROCESS_NAMES:
                return name
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def is_game_running() -> bool:
    return find_game_process() is not None
