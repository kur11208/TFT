from typing import List
from ..schemas import AnalyzeRequest

FRONTLINE_TAGS = {
    # 日本語
    "ヴァンガード", "バスティオン", "マローダー", "前衛",
    # English (後方互換)
    "Guardian", "Tank", "Frontline", "Bruiser", "Vanguard", "Bastion", "Marauder",
}
BACKLINE_TAGS = {
    # 日本語
    "スナイパー", "ヴォイジャー", "チャレンジャー", "キャリー",
    # English (後方互換)
    "Mage", "Carry", "Arcanist", "Duelist", "Rapidfire", "Invoker", "Ranger", "Sniper", "Voyager", "Challenger",
}


def calc_board_strength(req: AnalyzeRequest) -> int:
    score = 0
    board = req.board
    level = req.level
    hp = req.hp
    gold = req.gold

    # 盤面の埋まり具合（レベル分の枠に対する割合）
    if level > 0:
        fill_ratio = len(board) / level
        score += int(min(fill_ratio, 1.0) * 20)

    # 2つ星・3つ星ボーナス
    for unit in board:
        if unit.stars == 2:
            score += 5
        elif unit.stars >= 3:
            score += 15

    # 前衛枚数（最大16点）
    frontline_count = sum(1 for u in board if any(t in FRONTLINE_TAGS for t in u.tags))
    score += min(frontline_count * 4, 16)

    # 後衛火力枚数（最大16点）
    backline_count = sum(1 for u in board if any(t in BACKLINE_TAGS for t in u.tags))
    score += min(backline_count * 4, 16)

    # レベルボーナス
    score += min(level * 2, 16)

    # HP余裕ボーナス
    if hp >= 80:
        score += 8
    elif hp >= 50:
        score += 4

    # Gold余裕ボーナス
    if gold >= 50:
        score += 8
    elif gold >= 30:
        score += 4

    return min(score, 100)
