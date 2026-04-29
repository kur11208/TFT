import os
import re
from collections import Counter
import cv2
import numpy as np
import pytesseract
from typing import Optional, Tuple

# --- Tesseract path (Windows) ---
_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(
        os.environ.get("USERNAME", "")
    ),
]

def _find_tesseract() -> Optional[str]:
    for p in _TESSERACT_CANDIDATES:
        if os.path.exists(p):
            return p
    import shutil
    return shutil.which("tesseract")

_tess_path = _find_tesseract()
if _tess_path:
    pytesseract.pytesseract.tesseract_cmd = _tess_path

_LOCAL_TESSDATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "tessdata"))
_LOCAL_ENG_DATA = os.path.join(_LOCAL_TESSDATA_DIR, "eng.traineddata")
_LOCAL_JPN_DATA = os.path.join(_LOCAL_TESSDATA_DIR, "jpn.traineddata")
_LOCAL_TESSDATA_ARG = _LOCAL_TESSDATA_DIR.replace("\\", "/")


def _build_tesseract_config(base: str, *, text_mode: bool = False) -> str:
    parts = [base]
    if os.path.isdir(_LOCAL_TESSDATA_DIR):
        parts.append(f"--tessdata-dir {_LOCAL_TESSDATA_ARG}")
    if text_mode:
        langs = []
        if os.path.exists(_LOCAL_JPN_DATA):
            langs.append("jpn")
        if os.path.exists(_LOCAL_ENG_DATA) or _tess_path:
            langs.append("eng")
        if langs:
            parts.append(f'-l {"+".join(dict.fromkeys(langs))}')
    return " ".join(parts)

def is_tesseract_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


# --- Preprocessing ---

def _upscale(img: np.ndarray, scale: float) -> np.ndarray:
    h, w = img.shape[:2]
    return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def _to_gray_thresh(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _isolate_bright(img_bgr: np.ndarray, threshold: int = 140) -> np.ndarray:
    """Keep bright pixels (white/light text). Adaptive threshold fallback."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # Try fixed threshold first; if result is mostly black, use adaptive
    _, fixed = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    if fixed.mean() < 5:
        # Very dark image — drop threshold and try adaptive
        _, fixed = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    return fixed


def _isolate_gold_text(img_bgr: np.ndarray) -> np.ndarray:
    """Isolate yellow/gold and white text (gold counter)."""
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    yellow = cv2.inRange(hsv, (15, 80, 140), (38, 255, 255))
    white  = cv2.inRange(hsv, (0, 0, 190), (180, 60, 255))
    return cv2.bitwise_or(yellow, white)


def preprocess_for_number(img_bgr: np.ndarray, field: str = "") -> np.ndarray:
    """Preprocessing for digit-only regions. field-aware color extraction."""
    img = _upscale(img_bgr, scale=4.0)
    if field == "gold":
        mask = _isolate_gold_text(img)
        if mask.mean() > 1.0:
            return mask
        # Fallback: CLAHE + Otsu when color isolation yields nothing
        return _to_gray_thresh(img)
    mask = _isolate_bright(img, threshold=120)
    if mask.mean() > 1.0:
        return mask
    return _to_gray_thresh(img)


def preprocess_for_text(img_bgr: np.ndarray) -> np.ndarray:
    """General preprocessing for text regions (Stage, unit names)."""
    img = _upscale(img_bgr, scale=3.0)
    return _to_gray_thresh(img)


def _text_variants(img_bgr: np.ndarray) -> list[np.ndarray]:
    upscaled = _upscale(img_bgr, scale=3.0)
    gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)
    bright = _isolate_bright(upscaled, threshold=140)
    kernel = np.ones((2, 2), np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel)
    return [
        _to_gray_thresh(img_bgr),
        gray,
        bright,
    ]


def preprocess_for_stage(img_bgr: np.ndarray) -> np.ndarray:
    """Stage text sits on a dark banner, so an aggressive high-contrast pass is fine."""
    img = _upscale(img_bgr, scale=5.0)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def preprocess_for_stage_bright(img_bgr: np.ndarray) -> np.ndarray:
    """Fallback pass that isolates bright HUD digits more aggressively."""
    img = _upscale(img_bgr, scale=5.0)
    mask = _isolate_bright(img, threshold=135)
    kernel = np.ones((2, 2), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)


def _parse_stage_parts(stage: str) -> Optional[Tuple[int, int]]:
    match = re.fullmatch(r"(\d+)-(\d+)", stage.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _stage_to_index(stage: str) -> Optional[int]:
    parts = _parse_stage_parts(stage)
    if not parts:
        return None
    stage_num, round_num = parts
    if not (1 <= stage_num <= 9 and 1 <= round_num <= 7):
        return None
    return stage_num * 10 + round_num


def _stage_distance(candidate: str, expected: str) -> Optional[int]:
    candidate_idx = _stage_to_index(candidate)
    expected_idx = _stage_to_index(expected)
    if candidate_idx is None or expected_idx is None:
        return None
    return abs(candidate_idx - expected_idx)


# --- OCR functions ---

def ocr_number(img_bgr: np.ndarray, field: str = "") -> Tuple[Optional[int], float]:
    """Read a single integer from a region. Returns (value, confidence 0-1)."""
    proc = preprocess_for_number(img_bgr, field=field)
    cfg = _build_tesseract_config("--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789")

    def valid_value(value: int) -> bool:
        if field == "hp":
            return 0 <= value <= 100
        if field == "gold":
            return 0 <= value <= 99
        if field == "level":
            return 1 <= value <= 10
        return True

    raw = pytesseract.image_to_string(proc, config=cfg)
    digits = re.sub(r"\D", "", raw)
    if digits:
        value = int(digits)
        if valid_value(value) and not (field == "hp" and len(digits) < 2):
            return value, 0.5 if len(digits) >= 2 else 0.45

    data = pytesseract.image_to_data(proc, config=cfg, output_type=pytesseract.Output.DICT)
    texts, confs = [], []
    for text, conf in zip(data["text"], data["conf"]):
        c = int(conf)
        if c > 0 and text.strip():
            texts.append(text.strip())
            confs.append(c / 100.0)
    combined = "".join(texts)
    digits = re.sub(r"\D", "", combined)
    if field == "hp" and len(digits) < 2:
        digits = ""
    if digits and not valid_value(int(digits)):
        digits = ""
    if not digits:
        if field == "gold":
            candidates: list[str] = []
            width = proc.shape[1]
            for trim_ratio in (0.0, 0.08, 0.15, 0.22, 0.30):
                start_x = int(width * trim_ratio)
                sub = proc[:, start_x:]
                raw = pytesseract.image_to_string(sub, config=cfg)
                cand = re.sub(r"\D", "", raw)
                if cand and len(cand) <= 2 and int(cand) <= 99:
                    candidates.append(cand.lstrip("0") or "0")
            if candidates:
                best = Counter(candidates).most_common(1)[0][0]
                return int(best), 0.45
        raw = pytesseract.image_to_string(proc, config=cfg)
        digits = re.sub(r"\D", "", raw)
        if digits:
            if field == "hp" and len(digits) < 2:
                return None, 0.0
            if not valid_value(int(digits)):
                return None, 0.0
            # HUD digits are tiny; image_to_data often drops them while
            # image_to_string still returns a usable result.
            return int(digits), 0.5 if len(digits) >= 2 else 0.45
        return None, 0.0
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return int(digits), avg_conf


def ocr_text(img_bgr: np.ndarray) -> Tuple[str, float]:
    """Read a text string from a region. Returns (text, confidence 0-1)."""
    cfgs = (
        _build_tesseract_config("--psm 8 --oem 3", text_mode=True),
        _build_tesseract_config("--psm 7 --oem 3", text_mode=True),
        _build_tesseract_config("--psm 6 --oem 3", text_mode=True),
    )
    best_text = ""
    best_conf = 0.0
    best_score = 0.0
    for proc in _text_variants(img_bgr):
        for cfg in cfgs:
            data = pytesseract.image_to_data(proc, config=cfg, output_type=pytesseract.Output.DICT)
            texts, confs = [], []
            for text, conf in zip(data["text"], data["conf"]):
                c = int(conf)
                if c > 15 and text.strip():
                    texts.append(text.strip())
                    confs.append(c / 100.0)
            text = " ".join(texts).strip()
            if text:
                avg_conf = sum(confs) / len(confs) if confs else 0.0
                score = avg_conf + min(0.25, len(text) * 0.01)
                if score > best_score:
                    best_text = text
                    best_conf = avg_conf
                    best_score = score
            raw = pytesseract.image_to_string(proc, config=cfg).strip()
            if raw:
                score = 0.2 + min(0.25, len(raw) * 0.01)
                if score > best_score:
                    best_text = raw
                    best_conf = 0.35
                    best_score = score
    return best_text, best_conf


def ocr_stage(img_bgr: np.ndarray, expected_stage: Optional[str] = None) -> Tuple[str, float]:
    """Read TFT stage text like '3-5' from the top banner."""
    bright = preprocess_for_stage_bright(img_bgr)
    stage = preprocess_for_stage(img_bgr)
    psm7 = _build_tesseract_config("--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789-")
    psm8 = _build_tesseract_config("--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789-")
    attempts = (
        ("bright", bright, "psm7", psm7, 0.0, 0.84),
        ("stage", stage, "psm7", psm7, 0.0, 0.78),
        ("bright", bright, "psm7", psm7, 0.08, 0.72),
        ("stage", stage, "psm8", psm8, 0.0, 0.64),
    )
    weighted_scores: Counter[str] = Counter()
    hit_counts: Counter[str] = Counter()

    for variant_name, proc, cfg_name, cfg, trim_ratio, base_confidence in attempts:
        width = proc.shape[1]
        start_x = int(width * trim_ratio)
        end_x = width - int(width * min(trim_ratio * 0.35, 0.12))
        if end_x <= start_x + 8:
            continue
        sub = proc[:, start_x:end_x]
        raw = pytesseract.image_to_string(sub, config=cfg).strip()
        parsed = parse_stage(raw)
        if not parsed:
            continue

        weight = 1.0
        if trim_ratio == 0.0:
            weight += 0.2
        if variant_name == "bright":
            weight += 0.2
        if cfg_name == "psm7":
            weight += 0.1

        if expected_stage:
            dist = _stage_distance(parsed, expected_stage)
            if dist == 0:
                return parsed, min(base_confidence + 0.06, 0.90)
            if dist == 1:
                weight += 0.45
            elif dist == 2:
                weight += 0.2
            elif dist is not None and dist >= 4:
                weight -= 0.55

        weighted_scores[parsed] += weight
        hit_counts[parsed] += 1

    if weighted_scores:
        best_stage, best_score = max(weighted_scores.items(), key=lambda item: item[1])
        hits = hit_counts[best_stage]
        confidence = 0.38 + min(0.42, hits * 0.08 + max(0.0, best_score - 1.0) * 0.05)
        if expected_stage:
            dist = _stage_distance(best_stage, expected_stage)
            if dist == 0:
                confidence += 0.08
            elif dist == 1:
                confidence += 0.04
        return best_stage, min(confidence, 0.88)
    return "", 0.0


def parse_stage(raw: str) -> Optional[str]:
    """Extract 'X-Y' stage format from raw OCR text. Validates against TFT stage range.
    Handles leading garbage digits (e.g. '94-7' → '4-7') common when adjacent UI bleeds in.
    """
    for m in re.finditer(r"(\d+)[^0-9](\d+)", raw):
        s_str = m.group(1)
        round_num = int(m.group(2))
        if not (1 <= round_num <= 7):
            continue
        # Try the full first group, then strip leading digits one by one
        for i in range(len(s_str)):
            stage_num = int(s_str[i:])
            if 1 <= stage_num <= 9:
                return f"{stage_num}-{round_num}"
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 2:
        for i in range(len(digits) - 1):
            stage_num = int(digits[i])
            round_num = int(digits[i + 1])
            if 1 <= stage_num <= 9 and 1 <= round_num <= 7:
                return f"{stage_num}-{round_num}"
    return None
