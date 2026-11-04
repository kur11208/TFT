import asyncio
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel

from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ShopRecommendation,
    CutCandidate,
    SituationAction,
    AugmentChoiceRequest,
    AugmentChoiceResponse,
    ForgeAdviceRequest,
    ForgeAdviceResponse,
    GodsChoiceRequest,
    GodsChoiceResponse,
    GodBoonRequest,
    GodBoonResponse,
)
from .logic.scoring import calc_board_strength, FRONTLINE_TAGS, BACKLINE_TAGS
from .logic.comps import calc_top_comp, load_comps
from .logic.economy import calc_economy_plan
from .logic.augments import calc_augment_recommendations
from .logic.board_advice import calc_board_advice
from .logic.item_advisor import (
    build_item_plan_summary,
    calc_augment_choice,
    calc_forge_choice,
    calc_god_boon,
    calc_gods_choice,
    calc_situation_actions,
)
from .auto_screenshot import get_status as get_auto_screenshot_status, start_worker as start_auto_screenshot_worker, stop_worker as stop_auto_screenshot_worker, update_config as update_auto_screenshot_config
from .state_normalizer import normalize_gep_state

app = FastAPI(title="TFT Advisor API", version="0.2.0")

_AUGMENT_STAGES = {"2-1", "3-2", "4-2"}
_GOD_STAGES = {"2-4", "3-4", "4-4"}
_GOD_BOON_STAGES = {"4-7"}
_GAME_STATUS_CACHE_TTL_SEC = 2.0
_game_status_cache: Dict[str, Any] = {"running": False, "process": None}
_game_status_cache_at = 0.0


def _normalize_stage_value(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    parts = text.split("-", 1)
    if len(parts) != 2:
        return None
    try:
        stage_num = int(parts[0])
        round_num = int(parts[1])
    except ValueError:
        return None
    if not (1 <= stage_num <= 9 and 1 <= round_num <= 7):
        return None
    return f"{stage_num}-{round_num}"


def _read_live_stage() -> Optional[str]:
    snapshot = _current_gep_snapshot()
    stage = _normalize_stage_value((snapshot.get("state") or {}).get("stage"))
    if stage:
        return stage

    try:
        from .lcu.client import get_lcu_client
        from .lcu.tft_reader import read_tft_state

        state = read_tft_state(lcu_client=get_lcu_client()).get("state") or {}
        return _normalize_stage_value(state.get("stage"))
    except Exception:
        return None


def _selection_type_for_stage(stage: Optional[str]) -> Optional[str]:
    if stage in _AUGMENT_STAGES:
        return "augment"
    if stage in _GOD_STAGES:
        return "god"
    if stage in _GOD_BOON_STAGES:
        return "godboon"
    return None


def _selection_type_from_counts(
    stage_type: Optional[str],
    aug_count: int,
    god_count: int,
    forge_count: int,
) -> Optional[str]:
    if god_count >= 1:
        return "god"
    if stage_type == "augment" and aug_count >= 2:
        return "augment"
    if stage_type == "godboon":
        return "godboon"
    if stage_type is None and forge_count >= 2:
        return "forge"
    return None


def _ocr_region_name(full, rect: Optional[dict], *, conf_threshold: float = 0.16) -> str:
    if not rect:
        return ""

    from .capture.ocr import ocr_text

    x = max(0, int(rect["x"]))
    y = max(0, int(rect["y"]))
    w = max(1, int(rect["w"]))
    h = max(1, int(rect["h"]))
    crop = full[y:y + h, x:x + w]
    if crop.size == 0:
        return ""

    text, conf = ocr_text(crop)
    return text.strip() if conf >= conf_threshold else ""


def _read_augment_choices_from_frame(full) -> List[str]:
    from .capture.augment_detector import find_regions
    from .capture.augment_matcher import icons_available as aug_icons_ok, match_augment
    from .capture.selection_matcher import resolve_augment_name

    names: List[str] = []
    for region in find_regions(full):
        name_rect = region["name"]
        icon_rect = region["icon"]
        raw_text = _ocr_region_name(full, name_rect, conf_threshold=0.12)
        resolved_text = resolve_augment_name(raw_text) or raw_text

        x = icon_rect["x"]
        y = icon_rect["y"]
        w = icon_rect["w"]
        h = icon_rect["h"]
        icon_crop = full[y:y + h, x:x + w]

        matched_name = ""
        if aug_icons_ok() and icon_crop.size:
            matched_name, _ = match_augment(icon_crop, resolved_text)
        names.append(matched_name or resolved_text)
    return names


def _read_named_choices_from_regions(full, regions: List[Optional[dict]], resolver) -> List[str]:
    out: List[str] = []
    for rect in regions:
        raw_text = _ocr_region_name(full, rect)
        out.append(resolver(raw_text) or raw_text)
    return out


def _clip_rect(rect: dict, frame_w: int, frame_h: int) -> Optional[dict]:
    x = max(0, int(rect["x"]))
    y = max(0, int(rect["y"]))
    w = max(1, int(rect["w"]))
    h = max(1, int(rect["h"]))
    if x >= frame_w or y >= frame_h:
        return None
    w = min(w, frame_w - x)
    h = min(h, frame_h - y)
    return {"x": x, "y": y, "w": w, "h": h}


def _expanded_rect(rect: dict, frame_w: int, frame_h: int, *, dx: int = 0, dy: int = 0, grow_x: float = 0.45, grow_y: float = 0.35) -> Optional[dict]:
    grow_w = int(rect["w"] * grow_x)
    grow_h = int(rect["h"] * grow_y)
    return _clip_rect(
        {
            "x": int(rect["x"]) - grow_w + dx,
            "y": int(rect["y"]) - grow_h + dy,
            "w": int(rect["w"]) + grow_w * 2,
            "h": int(rect["h"]) + grow_h * 2,
        },
        frame_w,
        frame_h,
    )


def _god_region_groups(full) -> List[List[dict]]:
    from .capture.regions import scale_regions_to_screen

    frame_h, frame_w = full.shape[:2]
    scaled = scale_regions_to_screen(frame_w, frame_h)
    groups: List[List[dict]] = []

    for index, fallback_x in ((1, 0.25), (2, 0.53)):
        candidates: List[dict] = []
        base = scaled.get(f"god_name_{index}")
        if base:
            for dy_ratio in (-0.12, -0.06, 0.0, 0.06, 0.12):
                rect = _expanded_rect(base, frame_w, frame_h, dy=int(frame_h * dy_ratio))
                if rect:
                    candidates.append(rect)

        for rect in (
            {"x": int(frame_w * fallback_x), "y": int(frame_h * 0.22), "w": int(frame_w * 0.24), "h": int(frame_h * 0.18)},
            {"x": int(frame_w * (fallback_x - 0.04)), "y": int(frame_h * 0.32), "w": int(frame_w * 0.31), "h": int(frame_h * 0.22)},
            {"x": int(frame_w * (fallback_x - 0.06)), "y": int(frame_h * 0.18), "w": int(frame_w * 0.36), "h": int(frame_h * 0.42)},
        ):
            clipped = _clip_rect(rect, frame_w, frame_h)
            if clipped:
                candidates.append(clipped)
        groups.append(candidates)

    return groups


def _read_named_choices_from_region_groups(full, region_groups: List[List[dict]], resolver, *, resolved_only: bool = False) -> List[str]:
    out: List[str] = []
    for regions in region_groups:
        fallback_raw = ""
        resolved_name = ""
        for rect in regions:
            raw_text = _ocr_region_name(full, rect, conf_threshold=0.08)
            if raw_text and not fallback_raw:
                fallback_raw = raw_text
            resolved_name = resolver(raw_text)
            if resolved_name:
                break
        out.append(resolved_name or ("" if resolved_only else fallback_raw))
    return out


# ===== Capture schemas =====

class CaptureResult(BaseModel):
    state: AnalyzeRequest
    raw_ocr: dict
    confidence: dict
    preview_b64: Optional[str] = None
    timestamp: str


class CaptureRequest(BaseModel):
    include_preview: bool = False
    existing_state: Optional[AnalyzeRequest] = None
    fast: bool = False


class AutoScreenshotConfig(BaseModel):
    enabled: Optional[bool] = None
    interval_sec: Optional[int] = None
    only_normal: Optional[bool] = None
    only_in_game: Optional[bool] = None

# Allow only the two local development origins by default.
# Overwolf/file:// uses an opaque (null) Origin. Enabling that mode intentionally
# requires explicit opt-in; it weakens browser-origin isolation.
_ALLOWED_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://[::1]:5173",
    "http://127.0.0.1:8010",
    "http://localhost:8010",
    "http://[::1]:8010",
}
_ALLOWED_ORIGINS.update(
    value.strip()
    for value in os.getenv("TFT_ALLOWED_ORIGINS", "").split(",")
    if value.strip()
)
if os.getenv("TFT_ALLOW_OPAQUE_ORIGIN", "").strip() == "1":
    _ALLOWED_ORIGINS.add("null")

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_ALLOWED_ORIGINS),
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def reject_untrusted_browser_origins(request: Request, call_next):
    # CORS alone does not block cross-origin side effects (CSRF).
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site", "")
    if (origin is not None and origin not in _ALLOWED_ORIGINS) or (
        origin is None and fetch_site == "cross-site"
    ):
        return JSONResponse({"detail": "Untrusted browser origin"}, status_code=403)
    return await call_next(request)



@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
def _startup_background_workers() -> None:
    start_auto_screenshot_worker()


@app.on_event("shutdown")
def _shutdown_background_workers() -> None:
    stop_auto_screenshot_worker()


# ===== Game process watcher =====

@app.get("/game/status")
def game_status():
    """ゲームプロセスが起動中かを返す（ポーリング用）。"""
    global _game_status_cache, _game_status_cache_at

    now = time.time()
    if now - _game_status_cache_at < _GAME_STATUS_CACHE_TTL_SEC:
        return _game_status_cache

    from .watcher import find_game_process

    proc = find_game_process()
    _game_status_cache = {"running": proc is not None, "process": proc}
    _game_status_cache_at = now
    return _game_status_cache


def _build_game_screen_state_payload() -> Dict[str, Any]:
    from .watcher import is_game_running

    if not is_game_running():
        state = "no_game"
    else:
        from .capture.screen_detector import detect as detect_screen
        state = detect_screen()

    live_stage = _read_live_stage()
    payload: Dict[str, Any] = {"state": state}
    if live_stage:
        payload["stage"] = live_stage

    stage_type = _selection_type_for_stage(live_stage)
    should_scan_selection = state == "selection" or (
        state != "no_game" and stage_type in {"augment", "god", "godboon"}
    )
    if not should_scan_selection:
        return payload

    try:
        from .capture.regions import scale_regions_to_screen
        from .capture.screenshot import capture_full
        from .capture.selection_matcher import (
            resolve_component_name,
            resolve_god_name,
        )

        full = capture_full()

        read_all = state == "selection" and stage_type is None
        read_augments = read_all or stage_type == "augment"
        read_gods = read_all or stage_type == "god"
        read_forge = read_all

        augments = _read_augment_choices_from_frame(full) if read_augments else ["", "", ""]
        payload["augments"] = augments

        regions = scale_regions_to_screen(full.shape[1], full.shape[0])
        gods = (
            _read_named_choices_from_region_groups(full, _god_region_groups(full), resolve_god_name, resolved_only=True)
            if read_gods else ["", ""]
        )
        forge_items = (
            _read_named_choices_from_regions(
                full,
                [regions.get(f"forge_name_{i}") for i in range(1, 4)],
                resolve_component_name,
            )
            if read_forge else ["", "", ""]
        )
        payload["gods"] = gods
        payload["forge_items"] = forge_items

        aug_count = sum(1 for x in augments if x)
        god_count = sum(1 for x in gods if x)
        forge_count = sum(1 for x in forge_items if x)

        selection_type = _selection_type_from_counts(stage_type, aug_count, god_count, forge_count)

        if selection_type is None:
            payload = {"state": "selection" if state == "selection" else "normal"}
            if live_stage:
                payload["stage"] = live_stage
        else:
            payload["state"] = "selection"
            payload["selection_type"] = selection_type
    except Exception:
        payload = {"state": "normal"}
        if live_stage:
            payload["stage"] = live_stage

    return payload


@app.get("/game/screen-state")
async def game_screen_state(request: Request):
    """
    SSE: TFT選択画面（オーグメント/金床/神）を輝度検知し、
    検知と同時にOCRを実行してオーグメント名を返す。
    """
    async def generate():
        last_payload_key: Optional[str] = None
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(1.5)
            try:
                payload = await asyncio.to_thread(_build_game_screen_state_payload)
                payload_key = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if payload_key == last_payload_key:
                    continue
                last_payload_key = payload_key

                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                continue

                from .watcher import is_game_running
                if not is_game_running():
                    state = "no_game"
                else:
                    from .capture.screen_detector import detect as detect_screen
                    state = detect_screen()

                live_stage = _read_live_stage()
                payload: Dict[str, Any] = {"state": state}
                if live_stage:
                    payload["stage"] = live_stage
                if state == "selection":
                    try:
                        from .capture.regions import scale_regions_to_screen
                        from .capture.screenshot import capture_full
                        from .capture.augment_matcher import match_augment, icons_available as aug_icons_ok
                        from .capture.augment_detector import find_regions
                        from .capture.selection_matcher import (
                            resolve_augment_name,
                            resolve_component_name,
                            resolve_god_name,
                        )

                        # フルスクリーンを1回キャプチャして使い回す
                        full = capture_full()

                        # テンプレートマッチングでカード位置を動的検出
                        full = capture_full()
                        card_regions = find_regions(full)

                        def _aug_slot_tm(idx: int) -> str:
                            cr = card_regions[idx]
                            ir = cr["icon"]
                            icon_img = full[ir["y"]:ir["y"]+ir["h"], ir["x"]:ir["x"]+ir["w"]]
                            raw_text = _ocr_region_name(full, cr["name"], conf_threshold=0.10)
                            ocr_raw = resolve_augment_name(raw_text) or raw_text
                            if aug_icons_ok():
                                name, _ = match_augment(icon_img, ocr_raw)
                                return name or ocr_raw
                            return ocr_raw

                        augments = [_aug_slot_tm(i) for i in range(min(3, len(card_regions)))]
                        while len(augments) < 3:
                            augments.append("")
                        payload["augments"] = augments

                        # 種別判定（god/forge はまだ固定座標OCR）
                        from .capture.regions import scale_regions_to_screen
                        regions = scale_regions_to_screen(full.shape[1], full.shape[0])
                        gods = _read_named_choices_from_regions(
                            full,
                            [regions.get(f"god_name_{i}") for i in range(1, 3)],
                            resolve_god_name,
                        )
                        forge_items = _read_named_choices_from_regions(
                            full,
                            [regions.get(f"forge_name_{i}") for i in range(1, 4)],
                            resolve_component_name,
                        )
                        payload["gods"] = gods
                        payload["forge_items"] = forge_items

                        aug_count = sum(1 for x in augments if x)
                        god_count = sum(1 for x in gods if x)
                        forge_count = sum(1 for x in forge_items  if x)
                        stage_type = _selection_type_for_stage(live_stage)

                        selection_type = _selection_type_from_counts(stage_type, aug_count, god_count, forge_count)

                        if selection_type is None:
                            payload = {"state": "normal"}
                            if live_stage:
                                payload["stage"] = live_stage
                        else:
                            payload["selection_type"] = selection_type
                    except Exception:
                        payload = {"state": "normal"}
                        if live_stage:
                            payload["stage"] = live_stage

                payload_key = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                if payload_key == last_payload_key:
                    continue
                last_payload_key = payload_key

                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            except Exception:
                pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/game/events")
async def game_events(request: Request):
    """
    SSE エンドポイント。ゲームの起動/終了を検知するたびにイベントを送信する。
    フロントエンドは EventSource で接続して自動キャプチャを ON/OFF できる。
    """
    from .watcher import find_game_process

    async def generate():
        last_state: Optional[bool] = None
        # 接続直後に現在の状態を即送信
        proc = find_game_process()
        running = proc is not None
        yield f"data: {json.dumps({'running': running, 'process': proc})}\n\n"
        last_state = running

        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(2)
            proc = find_game_process()
            running = proc is not None
            if running != last_state:
                yield f"data: {json.dumps({'running': running, 'process': proc})}\n\n"
                last_state = running

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ===== LCU endpoints =====

@app.get("/lcu/status")
def lcu_status():
    """League Clientに接続できているか確認。"""
    from .lcu.client import get_lcu_client, find_lockfile
    lf = find_lockfile()
    if not lf:
        return {"connected": False, "message": "League Clientが起動していません（lockfileが見つかりません）"}
    client = get_lcu_client()
    if not client:
        return {"connected": False, "message": "LCU接続失敗"}
    try:
        phase = client.game_phase()
        return {"connected": True, "phase": phase, "lockfile": lf}
    except Exception as e:
        return {"connected": False, "message": str(e)}


@app.get("/lcu/raw")
def lcu_raw():
    """port 2999 の allgamedata をそのまま返す（デバッグ用）。"""
    from .lcu.tft_reader import get_live_client_data
    data = get_live_client_data()
    if not data:
        return {"error": "port 2999 応答なし（ゲーム未起動）"}
    return data


@app.get("/lcu/game")
def lcu_game():
    """現在のTFTゲーム状態を取得。port 2999 (Live Client API) を常に試みる。"""
    from .lcu.client import get_lcu_client
    from .lcu.tft_reader import read_tft_state, get_live_client_data

    # port 2999 が応答しなければゲーム未起動と判断
    live = get_live_client_data()
    if not live:
        return {"in_game": False, "state": None, "message": "ゲーム未起動（port 2999 応答なし）"}

    client = get_lcu_client()  # 取れなくてもOK（port 2999 データを優先）
    data = read_tft_state(lcu_client=client)
    state = data['state']

    # gameTime か何らかのフィールドが取れていれば in_game=True
    has_data = bool(
        data['raw'].get('gameTime')
        or data['raw'].get('stage_api')
        or data['raw'].get('stage_ocr')
        or data['raw'].get('gold')
        or data['raw'].get('level')
    )
    return {
        "in_game": has_data,
        "state": state,
        "raw": data['raw'],
        "confidence": data['confidence'],
    }


# ===== Overwolf GEP endpoints =====

_gep_state: Dict[str, Any] = {}
_gep_last_update: float = 0.0
_gep_revision: int = 0


def _current_gep_snapshot() -> Dict[str, Any]:
    stale = time.time() - _gep_last_update > 60
    in_game = bool(_gep_state) and not stale
    normalized_state = normalize_gep_state(_gep_state if in_game else None)
    return {
        "source": "gep" if in_game else "none",
        "in_game": in_game,
        "state": normalized_state,
        "raw_state": _gep_state,
        "last_update": _gep_last_update,
        "revision": _gep_revision,
    }


@app.post("/gep/update")
async def gep_update(data: Dict[str, Any]):
    """Receive real-time game state from Overwolf GEP background script."""
    global _gep_state, _gep_last_update, _gep_revision
    _gep_state.update({k: v for k, v in data.items() if v is not None})
    _gep_last_update = time.time()
    _gep_revision += 1
    return {"ok": True}


@app.get("/game/state")
async def game_state():
    """Return current game state from GEP (or empty if no GEP data)."""
    return _current_gep_snapshot()


@app.get("/gep/stream")
async def gep_stream(request: Request):
    """SSE stream for near-real-time Overwolf GEP updates."""

    async def generate():
        last_revision = -1
        idle_cycles = 0

        while True:
            if await request.is_disconnected():
                break

            snapshot = _current_gep_snapshot()
            revision = int(snapshot.get("revision", 0))

            if revision != last_revision:
                last_revision = revision
                idle_cycles = 0
                yield f"data: {json.dumps(snapshot, ensure_ascii=False)}\n\n"
            else:
                idle_cycles += 1
                if idle_cycles >= 20:
                    idle_cycles = 0
                    yield ": keepalive\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ===== Capture endpoints =====

@app.get("/debug/screen")
def debug_screen():
    """輝度値・OCRリージョン確認用。検知が動いているか診断する。"""
    from .capture.screen_detector import brightness_debug
    from .capture.regions import scale_regions_to_screen
    from .capture.screenshot import get_screen_size, capture_region
    from .capture.ocr import ocr_text, ocr_number
    sw, sh = get_screen_size()
    brightness = brightness_debug()
    regions = scale_regions_to_screen(sw, sh)
    ocr_results = {}
    for key in ["stage", "level", "hp", "gold", "aug_name_1", "aug_name_2", "aug_name_3",
                "god_name_1", "god_name_2"]:
        r = regions.get(key)
        if not r:
            continue
        try:
            img = capture_region(r)
            if key in ("level", "hp", "gold"):
                val, conf = ocr_number(img, field=key)
                ocr_results[key] = {"value": val, "conf": round(conf, 2)}
            else:
                text, conf = ocr_text(img)
                ocr_results[key] = {"text": text, "conf": round(conf, 2)}
        except Exception as e:
            ocr_results[key] = {"error": str(e)}
    return {"screen_size": f"{sw}x{sh}", "brightness": brightness, "ocr": ocr_results}


@app.get("/vision/status")
def vision_status():
    """Return whether champion icon templates are loaded for vision matching."""
    from .capture.vision_matcher import icons_available, _load, _ICONS_DIR, _MAPPING_PATH
    import os
    icons = _load()
    return {
        "available": icons_available(),
        "icon_count": len(icons),
        "icons_dir": _ICONS_DIR,
        "mapping_exists": os.path.exists(_MAPPING_PATH),
    }


@app.post("/vision/download-icons")
def vision_download_icons():
    """Download champion icons from Data Dragon (runs synchronously, ~30s)."""
    try:
        from .scripts.download_icons import get_latest_version, download_icons, _MAPPING_OUT
        import json, os
        version = get_latest_version()
        mapping = download_icons(version)
        with open(_MAPPING_OUT, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        from .capture.vision_matcher import reload
        reload()
        return {"ok": True, "version": version, "count": len(mapping)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vision/reload-icons")
def vision_reload_icons():
    """Reload icon cache from disk (after manually adding icons)."""
    from .capture.vision_matcher import reload, _load
    reload()
    icons = _load()
    return {"ok": True, "icon_count": len(icons)}


@app.get("/capture/status")
def capture_status():
    """Check whether OCR (Tesseract) is available."""
    import pytesseract, os
    # パスを直接セット（環境によらず確実に動かす）
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for p in candidates:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
    try:
        ver = str(pytesseract.get_tesseract_version())
        ready = True
        msg = f"Tesseract OK (v{ver})"
    except Exception as e:
        ready = False
        msg = f"Tesseract エラー: {e}"
    return {"ocr_ready": ready, "message": msg}


@app.post("/capture", response_model=CaptureResult)
def capture(req: CaptureRequest):
    """
    Capture the screen, OCR the TFT UI regions, and return parsed game state.
    Fields that can't be read reliably are kept from existing_state (if provided).
    """
    try:
        from .capture.parser import capture_game_state, build_preview_image
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"キャプチャモジュールのインポートエラー: {e}")

    try:
        existing_state = req.existing_state
        if existing_state is None:
            try:
                gep_snapshot = _current_gep_snapshot()
                gep_state = gep_snapshot.get("state")
                if gep_snapshot.get("in_game") and gep_state:
                    existing_state = AnalyzeRequest(**gep_state)
            except Exception:
                existing_state = None
        if existing_state is None:
            try:
                from .lcu.client import get_lcu_client
                from .lcu.tft_reader import read_tft_state

                live_state = read_tft_state(lcu_client=get_lcu_client()).get("state")
                if live_state:
                    existing_state = AnalyzeRequest(**live_state)
            except Exception:
                existing_state = None
        result = capture_game_state(existing=existing_state, fast=req.fast)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"画面キャプチャ失敗: {e}")

    preview = None
    if req.include_preview:
        try:
            preview = build_preview_image(result["raw_ocr"], result["confidence"])
        except Exception:
            pass  # preview is optional; don't fail the whole request

    return CaptureResult(
        state=result["state"],
        raw_ocr=result["raw_ocr"],
        confidence=result["confidence"],
        preview_b64=preview,
        timestamp=datetime.now().isoformat(),
    )


@app.get("/capture/augments")
def capture_augments():
    """
    オーグメント選択画面から3枚のカード名をテンプレートマッチング+OCRで返す。
    """
    try:
        from .capture.screenshot import capture_full
        from .capture.ocr import ocr_text
        from .capture.augment_matcher import match_augment, icons_available as aug_icons_ok
        from .capture.augment_detector import find_regions, load_from_raw
        from .capture.selection_matcher import resolve_augment_name
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))

    load_from_raw()
    full = capture_full()
    card_regions = find_regions(full)
    names = []
    for cr in card_regions:
        nr = cr["name"]
        ir = cr["icon"]
        name_img = full[nr["y"]:nr["y"]+nr["h"], nr["x"]:nr["x"]+nr["w"]]
        icon_img  = full[ir["y"]:ir["y"]+ir["h"], ir["x"]:ir["x"]+ir["w"]]
        text, conf = ocr_text(name_img)
        ocr_raw = resolve_augment_name(text.strip() if conf >= 0.15 else "") or (text.strip() if conf >= 0.15 else "")
        if aug_icons_ok():
            matched, _ = match_augment(icon_img, ocr_raw)
            names.append(matched or ocr_raw)
        else:
            names.append(ocr_raw)

    return {"augments": names, "count": sum(1 for n in names if n)}


@app.get("/capture/preview")
def capture_preview():
    """Take a screenshot and return it annotated with capture regions (base64 PNG)."""
    try:
        from .capture.parser import build_preview_image
        img_b64 = build_preview_image({}, {})
        return {"image_b64": img_b64}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _do_capture_save(label: str = "manual") -> dict:
    """
    Sync helper: full OCR/vision capture → save annotated PNG + JSON.
    Safe to call from thread executor. label is appended to filename.
    """
    import base64 as _b64, json as _json_mod
    from datetime import datetime as _dt
    from .capture.parser import capture_game_state, build_preview_image

    try:
        existing_state = None
        try:
            gep_snapshot = _current_gep_snapshot()
            gep_state = gep_snapshot.get("state")
            if gep_snapshot.get("in_game") and gep_state:
                existing_state = AnalyzeRequest(**gep_state)
        except Exception:
            existing_state = None
        try:
            if existing_state is None:
                from .lcu.client import get_lcu_client
                from .lcu.tft_reader import read_tft_state

                live_state = read_tft_state(lcu_client=get_lcu_client()).get("state")
                if live_state:
                    existing_state = AnalyzeRequest(**live_state)
        except Exception:
            pass
        result = capture_game_state(existing=existing_state)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    try:
        preview_b64 = build_preview_image(result["raw_ocr"], result["confidence"])
    except Exception as e:
        return {"ok": False, "error": f"preview: {e}"}

    save_dir = _os.path.join(_os.path.dirname(__file__), "../../screenshots")
    _os.makedirs(save_dir, exist_ok=True)
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    png_path  = _os.path.join(save_dir, f"capture_{ts}_{label}.png")
    json_path = _os.path.join(save_dir, f"capture_{ts}_{label}.json")

    with open(png_path, "wb") as f:
        f.write(_b64.b64decode(preview_b64))

    save_data = {
        "timestamp": ts, "label": label,
        "state": result["state"].model_dump(),
        "raw_ocr": result["raw_ocr"],
        "confidence": result["confidence"],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        _json_mod.dump(save_data, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "png": _os.path.abspath(png_path),
        "json": _os.path.abspath(json_path),
        "timestamp": ts,
        "label": label,
        "summary": {
            "board": [u.name for u in result["state"].board],
            "bench": [u.name for u in result["state"].bench],
            "shop":  [u.name for u in result["state"].shop],
            "items": list(result["state"].items),
            "augments": list(result["state"].augments),
            "stage": result["state"].stage,
            "level": result["state"].level,
            "hp":    result["state"].hp,
            "gold":  result["state"].gold,
        },
        "low_confidence": {
            k: round(v, 2)
            for k, v in result["confidence"].items()
            if result["raw_ocr"].get(k) and v < 0.5
        },
    }


@app.post("/capture/screenshot")
def capture_screenshot():
    """スクリーンショットをそのまま保存（アノテーションなし）。"""
    from datetime import datetime as _dt
    from PIL import ImageGrab as _ImageGrab

    try:
        image = _ImageGrab.grab(include_layered_windows=True, all_screens=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"capture failed: {e}")
    if image is None:
        raise HTTPException(status_code=500, detail="capture failed")

    save_dir = _os.path.join(_os.path.dirname(__file__), "../../screenshots")
    _os.makedirs(save_dir, exist_ok=True)
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    path = _os.path.abspath(_os.path.join(save_dir, f"cap_{ts}.png"))
    image.save(path)
    return {"ok": True, "file": path, "timestamp": ts, "label": "manual"}


@app.post("/capture/save")
def capture_save():
    """
    Run full OCR/vision capture, save annotated PNG + JSON to screenshots/ folder.
    Returns the saved file paths — call this from the overlay during gameplay.
    """
    result = _do_capture_save("manual")
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "unknown"))
    return result


@app.get("/capture/auto-save/status")
async def capture_auto_save_status():
    return get_auto_screenshot_status()


@app.put("/capture/auto-save/config")
async def capture_auto_save_config(config: AutoScreenshotConfig):
    return update_auto_screenshot_config(
        enabled=config.enabled,
        interval_sec=config.interval_sec,
        only_normal=config.only_normal,
        only_in_game=config.only_in_game,
    )


@app.get("/capture/regions")
def get_regions():
    """Return current region configuration."""
    from .capture.regions import load_regions
    return load_regions()


@app.get("/capture/shop-overlay-layout")
def get_shop_overlay_layout():
    """Return screen-scaled shop card regions for the fullscreen highlight overlay."""
    from .capture.regions import get_shop_overlay_regions
    from .capture.screenshot import get_screen_size

    screen_w, screen_h = get_screen_size()
    return {
        "screen_width": screen_w,
        "screen_height": screen_h,
        "slots": get_shop_overlay_regions(screen_w, screen_h),
    }


@app.put("/capture/regions")
def update_regions(data: dict):
    """Update region configuration (save to regions.json)."""
    from .capture.regions import save_regions
    save_regions(data)
    return {"ok": True}


@app.get("/comps")
def get_all_comps():
    """Return all comp definitions (for the Comps tier list page)."""
    return load_comps()


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    board_strength = calc_board_strength(req)
    top_comp = calc_top_comp(req)
    economy_plan = calc_economy_plan(req, board_strength, top_comp.id)
    shop_recs = _calc_shop_recommendations(req, top_comp)
    cut_candidates = _calc_cut_candidates(req, top_comp)
    item_plan = _calc_item_plan(req, top_comp)
    next_improvements = _calc_next_improvements(req, top_comp, board_strength)
    augment_recs = calc_augment_recommendations(req, top_comp)
    board_advice = calc_board_advice(req, top_comp)
    situation = [SituationAction(**a) for a in calc_situation_actions(req, top_comp.id, board_strength)]

    return AnalyzeResponse(
        boardStrength=board_strength,
        topComp=top_comp,
        economyPlan=economy_plan,
        shopRecommendations=shop_recs,
        cutCandidates=cut_candidates,
        itemPlan=item_plan,
        nextImprovements=next_improvements,
        augmentRecommendations=augment_recs,
        boardAdvice=board_advice,
        situationActions=situation,
    )


@app.post("/advise/augment", response_model=AugmentChoiceResponse)
def advise_augment(req: AugmentChoiceRequest):
    result = calc_augment_choice(req.choices, req.comp_id, req.stage)
    return AugmentChoiceResponse(
        recommended=result["recommended"],
        ranked=[{"name": r["name"], "score": r["score"], "reason": r["reason"]}
                for r in result["ranked"]],
    )


@app.post("/advise/forge", response_model=ForgeAdviceResponse)
def advise_forge(req: ForgeAdviceRequest):
    result = calc_forge_choice(req.choices, req.held_items, req.comp_id)
    return ForgeAdviceResponse(
        recommended=result["recommended"],
        ranked=[{"name": r["name"], "score": r["score"],
                 "reason": r["reason"], "builds": r["builds"]}
                for r in result["ranked"]],
    )


@app.post("/advise/gods", response_model=GodsChoiceResponse)
def advise_gods(req: GodsChoiceRequest):
    result = calc_gods_choice(req.gods_offered, req.comp_id, req.god_align, req.hp)
    return GodsChoiceResponse(
        recommended=result["recommended"],
        ranked=[{"name": r["name"], "score": r["score"], "reason": r["reason"]}
                for r in result["ranked"]],
    )


@app.post("/advise/god-boon", response_model=GodBoonResponse)
def advise_god_boon(req: GodBoonRequest):
    result = calc_god_boon(req.boons_offered, req.comp_id, req.god_align)
    return GodBoonResponse(
        recommended=result["recommended"],
        ranked=[{"name": r["name"], "score": r["score"], "reason": r["reason"]}
                for r in result["ranked"]],
    )


def _calc_shop_recommendations(req: AnalyzeRequest, top_comp) -> List[ShopRecommendation]:
    comps = load_comps()
    comp_data = next((c for c in comps if c["id"] == top_comp.id), None)

    board_tags = [tag for unit in req.board for tag in unit.tags]
    bench_tags = [tag for unit in req.bench for tag in unit.tags]
    frontline_count = sum(1 for t in board_tags if t in FRONTLINE_TAGS)
    board_names = {u.name for u in req.board} | {u.name for u in req.bench}

    recs: List[ShopRecommendation] = []
    for unit in req.shop:
        score = 0
        reasons: List[str] = []

        if comp_data:
            key_tags = set(comp_data.get("key_tags", []))
            fl_tags = set(comp_data.get("frontline_tags", []))
            all_comp_tags = key_tags | fl_tags
            tag_match = sum(1 for t in unit.tags if t in all_comp_tags)
            score += tag_match * 10
            if tag_match:
                reasons.append("構成一致")

        # ペアチェック（既存ユニットとの合わせ）
        if unit.name in board_names:
            score += 8
            reasons.append("pair(2つ星候補)")

        # 前衛不足補正
        if frontline_count < 2 and any(t in FRONTLINE_TAGS for t in unit.tags):
            score += 6
            reasons.append("前衛補強")

        # キャリー補正
        if any(t in BACKLINE_TAGS for t in unit.tags):
            score += 5
            reasons.append("キャリー候補")

        action = "buy" if score >= 18 else "consider" if score >= 8 else "skip"
        recs.append(ShopRecommendation(
            name=unit.name,
            score=score,
            reason=" / ".join(reasons) if reasons else "優先度は低い",
            action=action,
        ))

    recs.sort(key=lambda x: x.score, reverse=True)
    return recs


def _calc_cut_candidates(req: AnalyzeRequest, top_comp) -> List[CutCandidate]:
    comps = load_comps()
    comp_data = next((c for c in comps if c["id"] == top_comp.id), None)
    if not comp_data:
        return []

    key_tags = set(comp_data.get("key_tags", []))
    fl_tags = set(comp_data.get("frontline_tags", []))
    all_comp_tags = key_tags | fl_tags

    candidates: List[CutCandidate] = []
    for unit in req.board:
        if unit.items:
            continue

        reasons: List[str] = []
        tag_match = any(t in all_comp_tags for t in unit.tags)

        if not tag_match:
            reasons.append("構成一致度が低い")
        if unit.stars == 1:
            reasons.append("1つ星")
        if not unit.tags:
            reasons.append("役割不明")

        # 2つ以上の弱点がある、または構成不一致かつ1つ星
        if len(reasons) >= 2 or (not tag_match and unit.stars == 1):
            candidates.append(CutCandidate(
                name=unit.name,
                reason="、".join(reasons),
            ))

    return candidates


def _calc_item_plan(req: AnalyzeRequest, top_comp) -> str:
    item_summary = build_item_plan_summary(req, top_comp.id)
    if item_summary:
        return item_summary

    comps = load_comps()
    comp_data = next((c for c in comps if c["id"] == top_comp.id), None) or {}
    item_keywords = " ".join(str(k) for k in comp_data.get("item_keywords", []))
    items = req.items

    ap_count = sum(1 for item in items if any(kw in item for kw in [
        "Rod", "Tear", "Hat", "Needlessly", "Goddess", "Rabadon",
        "ロッド", "涙", "帽子", "デスキャップ", "ラバドン", "ブルーバフ"]))
    ad_count = sum(1 for item in items if any(kw in item for kw in [
        "Sword", "Bow", "B.F.", "Recurve",
        "剣", "弓", "デスブレード", "インフィニティ", "ラスト・ウィスパー"]))
    tank_count = sum(1 for item in items if any(kw in item for kw in [
        "Vest", "Belt", "Chain", "Null", "Negatron", "Giant",
        "チョッキ", "ベルト", "チェーン", "ウォーモグ", "ガーゴイル", "ソーンメイル"]))

    if any(keyword in item_keywords for keyword in ["AP", "魔力", "ロッド", "涙", "ブルーバフ", "ラバドン"]):
        if ap_count >= 2:
            return f"作る: {top_comp.carry or '主キャリー'}にAP装備。優先: ブルーバフ / ラバドン / ジュエルド。"
        return "素材: ロッド・涙を優先。APキャリー用に温存。"

    if any(keyword in item_keywords for keyword in ["AD", "Crit", "クリティカル", "BFソード", "リカーブボウ"]):
        if ad_count >= 2:
            return f"作る: {top_comp.carry or '主キャリー'}にAD装備。優先: デスブレード / IE / ラストウィスパー。"
        return "素材: BFソード・弓・グローブを優先。ADキャリー用に温存。"

    if tank_count >= 2:
        return "作る: 前衛にタンク装備。優先: ガーゴイル / サンファイア / ウォーモグ。"

    if any(keyword in item_keywords for keyword in ["Tank", "タンク", "HP", "ベルト"]):
        if tank_count >= 2:
            return "作る: 前衛にタンク装備。優先: ガーゴイル / サンファイア / ウォーモグ。"
        return "素材: チョッキ・ベルト・クロークを前衛用に温存。"

    if "Fast 9" in str(comp_data.get("play_style", "")):
        return "温存: 主キャリー用素材を残す。無理に序盤ユニットへ完成品を固定しない。"

    return "作る: 手持ち素材で主キャリーか前衛の完成品を1つ作る。"


def _calc_next_improvements(req: AnalyzeRequest, top_comp, board_strength: int) -> List[str]:
    improvements: List[str] = []
    comps = load_comps()
    comp_data = next((c for c in comps if c["id"] == top_comp.id), None) or {}
    min_level = int(comp_data.get("min_level", 7) or 7)
    play_style = str(comp_data.get("play_style", ""))
    board_tags = [tag for unit in req.board for tag in unit.tags]
    frontline_count = sum(1 for t in board_tags if t in FRONTLINE_TAGS)

    if frontline_count < 2:
        improvements.append("買う: 前衛をもう1-2枚追加")

    if req.level < min_level:
        if "リロール" in play_style:
            improvements.append(f"E: Lv{min_level}まで上げてからD")
        else:
            improvements.append(f"E: Lv{min_level}まで上げる")

    one_star_units = [u.name for u in req.board if u.stars == 1]
    if one_star_units:
        improvements.append(f"買う: {one_star_units[0]} など1つ星を2つ星にする")

    ds_count = board_tags.count("ダーク・スター")
    if ds_count > 0 and ds_count < 2 and "dark_star" in top_comp.id:
        improvements.append("買う: ダーク・スターをもう1枚")

    meeple_count = board_tags.count("ミープル")
    if meeple_count > 0 and meeple_count < 3 and "meeple" in top_comp.id:
        improvements.append("買う: ミープルを3体まで揃える")

    if board_strength < 55:
        improvements.append("D: コア駒と前衛を揃える")

    if len(req.board) < req.level:
        improvements.append(f"置く: 空きスロットを埋める（{len(req.board)}/{req.level}）")

    if req.streak <= 0:
        improvements.append("判断: 勝ちに行くならD、貯めるならホールド")

    return improvements[:5]


# ===== ビルド済みフロントエンドの静的配信（本番モード） =====
# build.bat 実行後に frontend/dist/ が存在する場合、
# http://127.0.0.1:8010/ でそのまま UI を開ける。
# 開発中は npm run dev (port 5173) を使う。
import os as _os
_dist = _os.path.join(_os.path.dirname(__file__), "../../frontend/dist")
if _os.path.isdir(_dist):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
