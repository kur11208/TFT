from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from ..capture.regions import scale_regions_to_screen

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _slot_groups() -> dict[str, list[str]]:
    return {
        "board": [f"portrait_board_r{row}_c{col}" for row in range(1, 5) for col in range(1, 8)],
        "bench": [f"portrait_bench_{idx}" for idx in range(1, 10)],
    }


def export_slot_crops(input_dir: str | Path, output_dir: str | Path) -> list[dict]:
    source = Path(input_dir)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    for image_path in sorted(source.glob("*.png")):
        img = cv2.imread(str(image_path))
        if img is None:
            continue
        height, width = img.shape[:2]
        regions = scale_regions_to_screen(width, height)
        screenshot_out = destination / image_path.stem
        screenshot_out.mkdir(parents=True, exist_ok=True)

        entry = {
            "source": str(image_path.resolve()),
            "width": width,
            "height": height,
            "groups": {},
        }
        for group, keys in _slot_groups().items():
            group_out = screenshot_out / group
            group_out.mkdir(exist_ok=True)
            files = []
            for key in keys:
                region = regions.get(key)
                if not region:
                    continue
                crop = img[region["y"]:region["y"] + region["h"], region["x"]:region["x"] + region["w"]]
                if crop.size == 0:
                    continue
                output_path = group_out / f"{key}.png"
                cv2.imwrite(str(output_path), crop)
                files.append(
                    {
                        "slot": key,
                        "path": str(output_path.resolve()),
                        "region": region,
                    }
                )
            entry["groups"][group] = files
        manifest.append(entry)

    with open(destination / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export board/bench slot crops from screenshots")
    parser.add_argument("--input-dir", default=str(_REPO_ROOT / "screenshots" / "data"))
    parser.add_argument("--output-dir", default=str(_REPO_ROOT / "screenshots" / "slot_crops"))
    args = parser.parse_args()
    manifest = export_slot_crops(args.input_dir, args.output_dir)
    print(f"exported {len(manifest)} screenshots to {Path(args.output_dir).resolve()}")


if __name__ == "__main__":
    main()
