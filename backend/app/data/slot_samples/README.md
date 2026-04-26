Place labeled board/bench crops here before training `slot_model.json`.

Expected layout:

```text
slot_samples/
  board/
    ChampionName/
      sample_001.png
  bench/
    ChampionName/
      sample_001.png
```

Optional:

- Add `__empty__` under `board/` or `bench/` for empty-slot negatives.
- Generate raw crops with `python -m app.scripts.export_slot_crops`.
