from __future__ import annotations

import hashlib
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

from .capture.screen_detector import detect as detect_screen
from .capture.screenshot import capture_full
from .watcher import is_game_running

_ROOT_DIR = Path(__file__).resolve().parents[2]
_DEFAULT_OUTPUT_DIR = _ROOT_DIR / "screenshots" / "data"

_lock = threading.Lock()
_stop_event = threading.Event()
_thread: threading.Thread | None = None

_state: dict[str, Any] = {
    "enabled": False,
    "interval_sec": 15,
    "only_normal": True,
    "only_in_game": True,
    "last_attempt_at": 0.0,
    "last_saved_at": 0.0,
    "last_saved_path": "",
    "last_screen_state": "unknown",
    "last_skip_reason": "",
    "last_frame_hash": "",
    "save_count": 0,
    "revision": 0,
}


def _now() -> float:
    return time.time()


def _touch_state(**updates: Any) -> None:
    with _lock:
        _state.update(updates)
        _state["revision"] = int(_state.get("revision", 0)) + 1


def _normalize_interval(value: Any, fallback: int = 15) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(2, min(parsed, 300))


def _frame_hash(bgr) -> str:
    if bgr is None or getattr(bgr, "size", 0) == 0:
        return ""
    small = cv2.resize(bgr, (48, 27), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return hashlib.sha1(gray.tobytes()).hexdigest()


def _snapshot() -> dict[str, Any]:
    with _lock:
        state = dict(_state)
    return {
        "enabled": bool(state["enabled"]),
        "interval_sec": int(state["interval_sec"]),
        "only_normal": bool(state["only_normal"]),
        "only_in_game": bool(state["only_in_game"]),
        "last_attempt_at": float(state["last_attempt_at"]),
        "last_saved_at": float(state["last_saved_at"]),
        "last_saved_path": str(state["last_saved_path"]),
        "last_screen_state": str(state["last_screen_state"]),
        "last_skip_reason": str(state["last_skip_reason"]),
        "last_frame_hash": str(state.get("last_frame_hash", "")),
        "save_count": int(state["save_count"]),
        "revision": int(state["revision"]),
        "output_dir": str(_DEFAULT_OUTPUT_DIR.resolve()),
    }


def get_status() -> dict[str, Any]:
    return _snapshot()


def update_config(
    *,
    enabled: bool | None = None,
    interval_sec: int | None = None,
    only_normal: bool | None = None,
    only_in_game: bool | None = None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if enabled is not None:
        updates["enabled"] = bool(enabled)
        updates["last_skip_reason"] = ""
    if interval_sec is not None:
        updates["interval_sec"] = _normalize_interval(interval_sec, int(_state["interval_sec"]))
    if only_normal is not None:
        updates["only_normal"] = bool(only_normal)
    if only_in_game is not None:
        updates["only_in_game"] = bool(only_in_game)
    if updates:
        _touch_state(**updates)
    return _snapshot()


def _save_frame(frame, *, prefix: str = "auto") -> str:
    _DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _DEFAULT_OUTPUT_DIR / f"{prefix}_{ts}.png"
    cv2.imwrite(str(path), frame)
    return str(path.resolve())


def _worker_loop() -> None:
    while not _stop_event.wait(1.0):
        state = _snapshot()
        if not state["enabled"]:
            continue

        now = _now()
        if now - state["last_attempt_at"] < state["interval_sec"]:
            continue
        _touch_state(last_attempt_at=now)

        if state["only_in_game"] and not is_game_running():
            _touch_state(last_skip_reason="game_not_running", last_screen_state="unknown")
            continue

        screen_state = "unknown"
        if state["only_normal"]:
            screen_state = detect_screen()
            if screen_state != "normal":
                _touch_state(last_screen_state=screen_state, last_skip_reason=f"screen_{screen_state}")
                continue

        frame = capture_full()
        if frame is None or getattr(frame, "size", 0) == 0:
            _touch_state(last_screen_state=screen_state, last_skip_reason="capture_failed")
            continue

        frame_hash = _frame_hash(frame)
        if frame_hash and frame_hash == state["last_frame_hash"]:
            _touch_state(last_screen_state=screen_state, last_skip_reason="duplicate_frame")
            continue

        try:
            saved_path = _save_frame(frame)
        except Exception:
            _touch_state(last_screen_state=screen_state, last_skip_reason="save_failed")
            continue

        _touch_state(
            last_saved_at=now,
            last_saved_path=saved_path,
            last_screen_state=screen_state or "normal",
            last_skip_reason="",
            last_frame_hash=frame_hash,
            save_count=int(state["save_count"]) + 1,
        )


def start_worker() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_worker_loop, name="auto-screenshot-worker", daemon=True)
    _thread.start()


def stop_worker() -> None:
    global _thread
    _stop_event.set()
    if _thread is not None and _thread.is_alive():
        _thread.join(timeout=2.0)
    _thread = None
