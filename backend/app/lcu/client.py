import os
import base64
from typing import Optional, Dict, Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TFT_QUEUE_IDS = {1090, 1100, 1130, 1160, 1165}

_LOCKFILE_CANDIDATES = [
    r"C:\Riot Games\League of Legends\lockfile",
    r"C:\Program Files\Riot Games\League of Legends\lockfile",
    r"C:\Program Files (x86)\Riot Games\League of Legends\lockfile",
    r"D:\Riot Games\League of Legends\lockfile",
    r"D:\Games\League of Legends\lockfile",
    r"E:\Riot Games\League of Legends\lockfile",
]


def find_lockfile() -> Optional[str]:
    for p in _LOCKFILE_CANDIDATES:
        if os.path.exists(p):
            return p
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                name = proc.info.get('name') or ''
                exe = proc.info.get('exe') or ''
                if 'LeagueClient' in name and exe:
                    lf = os.path.join(os.path.dirname(exe), 'lockfile')
                    if os.path.exists(lf):
                        return lf
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return None


def parse_lockfile(path: str) -> Dict[str, str]:
    with open(path, 'r') as f:
        content = f.read().strip()
    name, pid, port, password, protocol = content.split(':')
    return {'name': name, 'pid': pid, 'port': port, 'password': password, 'protocol': protocol}


class LCUClient:
    def __init__(self, port: str, password: str):
        self.base = f"https://127.0.0.1:{port}"
        token = base64.b64encode(f"riot:{password}".encode()).decode()
        self._session = requests.Session()
        self._session.headers['Authorization'] = f"Basic {token}"
        self._session.verify = False

    def get(self, path: str) -> Any:
        r = self._session.get(f"{self.base}{path}", timeout=3)
        r.raise_for_status()
        return r.json()

    def game_phase(self) -> str:
        try:
            return self.get('/lol-gameflow/v1/gameflow-phase')
        except Exception:
            return 'None'

    def game_session(self) -> Optional[Dict]:
        try:
            return self.get('/lol-gameflow/v1/session')
        except Exception:
            return None

    def is_tft_in_progress(self) -> bool:
        session = self.game_session()
        if not session:
            return False
        phase = session.get('phase', '')
        if phase not in ('InProgress', 'GameStart'):
            return False
        try:
            queue_id = int(session.get('gameData', {}).get('queue', {}).get('id', -1))
        except (TypeError, ValueError):
            return False
        return queue_id in TFT_QUEUE_IDS


def get_lcu_client() -> Optional[LCUClient]:
    lf = find_lockfile()
    if not lf:
        return None
    try:
        data = parse_lockfile(lf)
        return LCUClient(data['port'], data['password'])
    except Exception:
        return None
