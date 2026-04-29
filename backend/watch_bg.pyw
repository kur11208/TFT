"""
Background watcher for TFT Advisor.

Run without a console window via `.pyw`.

Behavior:
- Poll every 3 seconds for `League of Legends.exe` or `TFTGame.exe`
- Start the backend server if needed
- Open the browser when the game starts
- Stop the server when the game closes

Use `scripts/windows/register_startup.bat` to register it on Windows logon.
"""
import os
import subprocess
import sys
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(BASE_DIR, ".venv", "Scripts", "python.exe")

GAME_PROCESSES = {"League of Legends.exe", "TFTGame.exe"}
PORT = 8010
URL = f"http://localhost:{PORT}"

# Windows flag to hide the spawned console window.
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _game_running() -> bool:
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            try:
                if (p.info["name"] or "") in GAME_PROCESSES:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _server_alive() -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(f"{URL}/health", timeout=1)
        return True
    except Exception:
        return False


def _start_server() -> subprocess.Popen:
    return subprocess.Popen(
        [VENV_PYTHON, "-m", "uvicorn", "app.main:app", "--port", str(PORT)],
        cwd=BASE_DIR,
        creationflags=_NO_WINDOW,
    )


def _wait_for_server(timeout: int = 15) -> bool:
    for _ in range(timeout):
        time.sleep(1)
        if _server_alive():
            return True
    return False


def main() -> None:
    server: subprocess.Popen | None = None
    was_running = False

    while True:
        now_running = _game_running()

        if now_running and not was_running:
            if not _server_alive():
                server = _start_server()
                _wait_for_server()
            webbrowser.open(URL)

        elif not now_running and was_running:
            if server is not None:
                server.terminate()
                server = None

        was_running = now_running
        time.sleep(3)


if __name__ == "__main__":
    main()
