from ..schemas import AnalyzeRequest, EconomyPlan


def _get_comp_meta(comp_id: str) -> tuple[str, int]:
    try:
        from .comps import load_comps

        comp = next((c for c in load_comps() if c.get("id") == comp_id), None)
    except Exception:
        comp = None

    if not comp:
        return "", 7

    return str(comp.get("play_style", "")), int(comp.get("min_level", 7) or 7)


def calc_economy_plan(req: AnalyzeRequest, board_strength: int, top_comp_id: str) -> EconomyPlan:
    hp = req.hp
    gold = req.gold
    level = req.level
    streak = req.streak
    play_style, min_level = _get_comp_meta(top_comp_id)

    try:
        round_num = int(req.stage.split("-")[0])
    except (ValueError, IndexError):
        round_num = 3

    if hp <= 40 and board_strength < 50:
        return EconomyPlan(
            action="D: 全額ロールして即強化",
            reason=f"HP {hp} / 盤面 {board_strength}。利子より戦闘力を優先。",
        )

    if hp <= 55 and board_strength < 55:
        return EconomyPlan(
            action="D: 20-30Gロール",
            reason=f"HP {hp}。2つ星と前衛を増やして被ダメを止める。",
        )

    if "リロール" in play_style:
        if level < min_level:
            return EconomyPlan(
                action=f"E: Lv{min_level}まで上げる",
                reason=f"リロール開始レベルはLv{min_level}。今はDを押さない。",
            )
        if gold >= 50:
            return EconomyPlan(
                action="D: 50G維持でスローリロール",
                reason="余剰ゴールドだけ回して3つ星を狙う。",
            )
        return EconomyPlan(
            action="貯金: 50Gまで待つ",
            reason="利子ラインを作ってからDを押す。",
        )

    if ("Fast 9" in play_style or "fast9" in top_comp_id) and level < 9:
        return EconomyPlan(
            action="E: 50G維持でLv9へ",
            reason="Fast 9 構成。Dは押さず余剰ゴールドを経験値へ。",
        )

    if level < min_level and gold >= 30:
        return EconomyPlan(
            action=f"E: Lv{min_level}優先",
            reason=f"狙う構成の完成ラインはLv{min_level}。",
        )

    if round_num <= 2 and board_strength >= 65:
        return EconomyPlan(
            action="維持: 連勝盤面を崩さない",
            reason="序盤の盤面が強い。売却や不要なDはしない。",
        )

    if streak >= 3 and gold >= 40:
        return EconomyPlan(
            action="E: レベル優先を継続",
            reason=f"{streak}連勝中。レベルを上げて盤面の質を維持。",
        )

    return EconomyPlan(
        action="貯金: 次の利子ラインへ",
        reason="大きく崩れていない。10/20/30/40/50Gを優先。",
    )
