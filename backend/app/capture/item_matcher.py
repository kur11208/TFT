"""
アイテムベンチのアイコン識別。
TFTのコンポーネントアイテムはアイコンなのでOCRが使えない。
各コンポーネントの代表的なHSV色域でマッチングする。
"""
import cv2
import numpy as np
from typing import Optional

# コンポーネント → 代表HSV範囲 (lower, upper)
# TFT標準9種コンポーネント
_COMPONENT_COLOR: dict[str, tuple] = {
    "BFソード":      ((10, 60, 120),  (30, 255, 255)),   # オレンジ/金
    "リカーブボウ":  ((25, 80, 100),  (40, 220, 220)),   # 黄緑
    "ロッド":        ((140, 60, 120), (160, 255, 255)),   # 紫
    "涙":            ((100, 60, 120), (130, 255, 255)),   # 青
    "チョッキ":      ((5,  30, 60),   (25, 160, 200)),    # グレー/茶
    "ベルト":        ((0,  40, 40),   (15, 180, 160)),    # 暗赤
    "クローク":      ((80, 40, 60),   (110, 180, 200)),   # 青緑
    "グローブ":      ((15, 60, 60),   (35, 200, 180)),    # オレンジ茶
    "スパチュラ":    ((55, 80, 80),   (80, 255, 255)),    # 緑
}

_MIN_COLORED_PIXELS = 10  # マッチとみなす最低ピクセル数


def _count_hsv(img_bgr: np.ndarray, lower: tuple, upper: tuple) -> int:
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
    return int(np.sum(mask > 0))


def identify_component(img_bgr: np.ndarray) -> Optional[str]:
    """
    30x30 px 程度のアイテムアイコン画像を受け取り、最も近いコンポーネント名を返す。
    マッチしなければ None。
    """
    if img_bgr is None or img_bgr.size == 0:
        return None
    best_name, best_count = None, _MIN_COLORED_PIXELS
    for name, (lo, hi) in _COMPONENT_COLOR.items():
        cnt = _count_hsv(img_bgr, lo, hi)
        if cnt > best_count:
            best_count = cnt
            best_name = name
    return best_name
