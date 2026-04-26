import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.state_normalizer import normalize_gep_state  # noqa: E402


class NormalizeGepStateTests(unittest.TestCase):
    def test_normalizes_basic_fields_and_units(self) -> None:
        raw_state = {
            "stage": {"round": "3-2"},
            "level": "6",
            "health": "78",
            "gold": "34",
            "board": {
                "units": [
                    {"displayName": "Leona", "stars": 2},
                    {"id": "TFT17_Nasus", "tier": 1},
                ]
            },
            "bench": [{"championName": "Poppy", "star": 1}],
            "shop": [{"name": "Caitlyn"}, {"name": "Leona"}],
            "augments": [{"name": "Trade Sector"}, "Pandora's Items"],
        }

        state = normalize_gep_state(raw_state)

        self.assertEqual(state["stage"], "3-2")
        self.assertEqual(state["level"], 6)
        self.assertEqual(state["hp"], 78)
        self.assertEqual(state["gold"], 34)
        self.assertEqual([unit["name"] for unit in state["board"]], ["レオナ", "ナサス"])
        self.assertEqual([unit["stars"] for unit in state["board"]], [2, 1])
        self.assertEqual([unit["name"] for unit in state["bench"]], ["ポッピー"])
        self.assertEqual([unit["name"] for unit in state["shop"]], ["ケイトリン", "レオナ"])
        self.assertEqual(state["augments"], ["Trade Sector", "Pandora's Items"])

    def test_falls_back_to_request_defaults_for_invalid_values(self) -> None:
        raw_state = {
            "stage": "final-boss",
            "level": "unknown",
            "health": None,
            "gold": -5,
            "board": ["not-a-real-unit"],
            "bench": None,
            "shop": {},
        }

        state = normalize_gep_state(raw_state)

        self.assertEqual(state["stage"], "1-1")
        self.assertEqual(state["level"], 1)
        self.assertEqual(state["hp"], 100)
        self.assertEqual(state["gold"], 0)
        self.assertEqual(state["board"], [])
        self.assertEqual(state["bench"], [])
        self.assertEqual(state["shop"], [])

    def test_normalizes_overwolf_piece_maps_and_game_stage_fallback(self) -> None:
        expected = normalize_gep_state(
            {
                "stage": {"round": "4-2"},
                "level": "7",
                "health": "55",
                "gold": "19",
                "board": [
                    {"id": "TFT17_Leona", "tier": 2},
                    {"displayName": "Nasus", "stars": 1},
                ],
                "bench": [{"championName": "Poppy", "star": 2}],
                "shop": [{"id": "TFT17_Caitlyn"}, {"name": "Leona"}],
            }
        )

        raw_state = {
            "stage": "not-a-stage",
            "game_stage": {"round": "4-2"},
            "level": "7",
            "health": "55",
            "gold": "19",
            "board": {
                "board_pieces": {
                    "cell_1": {"id": "TFT17_Leona", "tier": 2},
                    "cell_2": {"displayName": "Nasus", "stars": 1},
                }
            },
            "bench": {
                "bench_pieces": {
                    "slot_1": {"championName": "Poppy", "star": 2},
                }
            },
            "shop": {
                "shop_pieces": {
                    "slot_1": {"id": "TFT17_Caitlyn"},
                    "slot_2": {"name": "Leona"},
                }
            },
        }

        state = normalize_gep_state(raw_state)

        self.assertEqual(state["stage"], "4-2")
        self.assertEqual(state["level"], 7)
        self.assertEqual(state["hp"], 55)
        self.assertEqual(state["gold"], 19)
        self.assertEqual(state["board"], expected["board"])
        self.assertEqual(state["bench"], expected["bench"])
        self.assertEqual(state["shop"], expected["shop"])


if __name__ == "__main__":
    unittest.main()
