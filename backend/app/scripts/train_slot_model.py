from __future__ import annotations

import argparse
from pathlib import Path

from ..capture.slot_classifier import build_slot_model

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="Train board/bench slot classifier from labeled crops")
    parser.add_argument("--samples-dir", default=str(_BACKEND_ROOT / "app" / "data" / "slot_samples"))
    parser.add_argument("--output", default=str(_BACKEND_ROOT / "app" / "data" / "current" / "slot_model.json"))
    args = parser.parse_args()

    model = build_slot_model(args.samples_dir, args.output)
    board_labels = len(model.get("board", {}))
    bench_labels = len(model.get("bench", {}))
    print(
        f"trained slot model at {Path(args.output).resolve()} "
        f"(board labels={board_labels}, bench labels={bench_labels})"
    )


if __name__ == "__main__":
    main()
