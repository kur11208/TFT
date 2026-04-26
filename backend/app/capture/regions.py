import json
import os
from typing import Optional

REGIONS_PATH = os.path.join(os.path.dirname(__file__), "../data/current/regions.json")

_BOARD_LOC = [
    (581, 651), (707, 651), (839, 651), (966, 651), (1091, 651), (1222, 651), (1349, 651),
    (532, 571), (660, 571), (776, 571), (903, 571), (1022, 571), (1147, 571), (1275, 571),
    (609, 494), (723, 494), (841, 494), (962, 494), (1082, 494), (1198, 494), (1318, 494),
    (557, 423), (673, 423), (791, 423), (907, 423), (1019, 423), (1138, 423), (1251, 423),
]
_BENCH_LOC = [
    (425, 777), (542, 777), (658, 777), (778, 777), (892, 777),
    (1010, 777), (1128, 777), (1244, 777), (1359, 777),
]
_BOARD_PORTRAIT_BOX = {"w": 130, "h": 135, "y_up": 112}
_BENCH_PORTRAIT_BOX = {"w": 116, "h": 130, "y_up": 108}


def load_regions() -> dict:
    with open(REGIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_regions(data: dict) -> None:
    with open(REGIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_region(name: str) -> Optional[dict]:
    data = load_regions()
    regions = dict(data.get("regions", {}))
    regions.update(_dynamic_portrait_regions())
    return regions.get(name)


def _rect_from_point(point: tuple[int, int], box: dict[str, int]) -> dict[str, int]:
    return {
        "x": point[0] - box["w"] // 2,
        "y": point[1] - box["y_up"],
        "w": box["w"],
        "h": box["h"],
    }


def _dynamic_portrait_regions() -> dict[str, dict[str, int | str]]:
    regions: dict[str, dict[str, int | str]] = {}

    for idx, point in enumerate(_BOARD_LOC, start=1):
        row = 4 - ((idx - 1) // 7)
        col = (idx - 1) % 7 + 1
        key = f"portrait_board_r{row}_c{col}"
        regions[key] = {
            **_rect_from_point(point, _BOARD_PORTRAIT_BOX),
            "desc": f"ボード row{row} col{col} ポートレート",
        }

    for idx, point in enumerate(_BENCH_LOC, start=1):
        key = f"portrait_bench_{idx}"
        regions[key] = {
            **_rect_from_point(point, _BENCH_PORTRAIT_BOX),
            "desc": f"ベンチ{idx} ポートレート",
        }

    return regions


def scale_regions_to_screen(current_w: int, current_h: int) -> dict:
    """Scale base 1920x1080 regions to actual screen resolution."""
    data = load_regions()
    base_w = data.get("base_width", 1920)
    base_h = data.get("base_height", 1080)
    sx = current_w / base_w
    sy = current_h / base_h
    raw_regions = dict(data.get("regions", {}))
    raw_regions.update(_dynamic_portrait_regions())
    scaled = {}
    for name, r in raw_regions.items():
        scaled[name] = {
            "x": int(r["x"] * sx),
            "y": int(r["y"] * sy),
            "w": int(r["w"] * sx),
            "h": int(r["h"] * sy),
        }
    return scaled
