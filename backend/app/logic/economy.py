from ..schemas import AnalyzeRequest, EconomyPlan


def calc_economy_plan(req: AnalyzeRequest, board_strength: int, top_comp_id: str) -> EconomyPlan:
    hp = req.hp
    gold = req.gold
    level = req.level
    streak = req.streak

    try:
        round_num = int(req.stage.split("-")[0])
    except (ValueError, IndexError):
        round_num = 3

    if hp <= 40 and board_strength < 50:
        return EconomyPlan(
            action="ロールして即時強化",
            reason=f"HP {hp} で盤面強度 {board_strength} は危険域。利子よりも今の戦闘力を優先したい。",
        )

    if hp <= 55 and board_strength < 55:
        return EconomyPlan(
            action="中量ロールで被ダメを止める",
            reason=f"HP {hp} に対して盤面が弱い。致命傷になる前に2つ星と前衛を増やしたい。",
        )

    if top_comp_id in ("dark_star_sniper", "space_groove_vanguard", "psionic_carry") and gold >= 30 and level < 8:
        return EconomyPlan(
            action="貯金してレベル優先",
            reason="Fast 8 系の構成。無理に回さず、Lv8到達を優先した方が最終盤面を作りやすい。",
        )

    if top_comp_id == "meeple_fast9" and gold >= 30 and level < 9:
        return EconomyPlan(
            action="貯金してLv9を目指す",
            reason="Fast 9 系の構成なので、30G以上を維持しながら経験値に回したい。",
        )

    if top_comp_id in ("nova_primordian", "stargazer_reroll"):
        if gold >= 50:
            return EconomyPlan(
                action="50G維持でスローリロール",
                reason="リロール構成なので、50Gの利子を保ちながら必要ユニットを集めたい。",
            )
        return EconomyPlan(
            action="まず50Gまで貯金",
            reason="リロールに入る前に利子ラインを作りたい。無駄な回しはまだ早い。",
        )

    if round_num <= 2 and board_strength >= 65:
        return EconomyPlan(
            action="連勝維持を優先",
            reason="序盤としてはかなり強い盤面。テンポを落とさず、連勝ボーナスを取りたい。",
        )

    if streak >= 3 and gold >= 40:
        return EconomyPlan(
            action="レベル優先を継続",
            reason=f"{streak}連勝中で経済も良い。レベルを上げて盤面の質をさらに伸ばしたい。",
        )

    return EconomyPlan(
        action="貯金しながら柔軟に進行",
        reason="現状は大きく崩れていない。次のショップやアイテムに合わせて判断したい。",
    )
