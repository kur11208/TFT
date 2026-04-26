"""
Forge component picker, augment choice advisor, and situation advisor.
"""
import json
import os
from typing import List, Optional, Dict

_AUGMENTS_PATH = os.path.join(os.path.dirname(__file__), "../data/current/augments.json")
_COMPS_PATH    = os.path.join(os.path.dirname(__file__), "../data/current/comps.json")

# ---- 正規化エイリアス（ゲーム内日本語表記 ↔ 内部キー） ----
ALIASES: Dict[str, str] = {
    # 長い表記 → 短い表記
    "ニードレスリー・ラージ・ロッド": "ロッド",
    "needlessly large rod": "ロッド", "nl rod": "ロッド", "rod": "ロッド",
    "ティア・オブ・ゴッデス": "涙",
    "tear of the goddess": "涙", "tear": "涙",
    "bfソード": "BFソード", "bf sword": "BFソード", "b.f.": "BFソード", "sword": "BFソード",
    "剣": "BFソード",
    "リカーブボウ": "リカーブボウ", "recurve bow": "リカーブボウ", "bow": "リカーブボウ", "弓": "リカーブボウ",
    "スパーリンググローブ": "グローブ", "sparring gloves": "グローブ", "glove": "グローブ", "グローブ": "グローブ",
    "チェーンベスト": "チョッキ", "chain vest": "チョッキ", "vest": "チョッキ", "チョッキ": "チョッキ",
    "ジャイアンツ・ベルト": "ベルト", "giant's belt": "ベルト", "giants belt": "ベルト", "belt": "ベルト", "ベルト": "ベルト",
    "ネガトロン・クローク": "クローク", "negatron cloak": "クローク", "cloak": "クローク",
    "チェーン": "クローク", "マント": "クローク",
    "スパチュラ": "スパチュラ", "spatula": "スパチュラ", "へら": "スパチュラ",
    "ロッド": "ロッド", "涙": "涙",
}

# ゲーム内表記（UIに表示する正式名）
COMPONENT_DISPLAY = {
    "ロッド":    "ニードレスリー・ラージ・ロッド",
    "涙":        "ティア・オブ・ゴッデス",
    "BFソード":  "BFソード",
    "リカーブボウ":"リカーブボウ",
    "グローブ":  "スパーリンググローブ",
    "チョッキ":  "チェーンベスト",
    "ベルト":    "ジャイアンツ・ベルト",
    "クローク":  "ネガトロン・クローク",
    "スパチュラ":"スパチュラ",
}

ALL_COMPONENT_KEYS = list(COMPONENT_DISPLAY.keys())

# ---- コンポーネントコンボ → 完成アイテム名 ----
COMBOS: Dict[frozenset, str] = {
    frozenset(["BFソード",    "BFソード"]):    "デスブレード",
    frozenset(["BFソード",    "リカーブボウ"]):"ギンソーのレイジブレード",
    frozenset(["BFソード",    "グローブ"]):    "インフィニティ・エッジ",
    frozenset(["BFソード",    "チョッキ"]):    "ブラッドサースター",
    frozenset(["BFソード",    "ベルト"]):      "ステラックの篭手",
    frozenset(["BFソード",    "涙"]):          "ヘクステック・ガンブレード",
    frozenset(["BFソード",    "クローク"]):    "クイックシルバー",
    frozenset(["BFソード",    "ロッド"]):      "ナイトの縁",

    frozenset(["リカーブボウ","リカーブボウ"]):"ラピッドファイア・キャノン",
    frozenset(["リカーブボウ","グローブ"]):    "ラスト・ウィスパー",
    frozenset(["リカーブボウ","チョッキ"]):    "サンファイア・ケープ",
    frozenset(["リカーブボウ","ベルト"]):      "タイタンの決意",
    frozenset(["リカーブボウ","涙"]):          "ナッシャーの歯牙",

    frozenset(["ロッド",      "ロッド"]):      "ラバドンのデスキャップ",
    frozenset(["ロッド",      "涙"]):          "ブルーバフ",
    frozenset(["ロッド",      "グローブ"]):    "ジュエルド・ガントレット",
    frozenset(["ロッド",      "チョッキ"]):    "アイオニック・スパーク",
    frozenset(["ロッド",      "ベルト"]):      "リデンプション",
    frozenset(["ロッド",      "クローク"]):    "ドラゴンクロウ",

    frozenset(["涙",          "涙"]):          "蒼者の穂先",
    frozenset(["涙",          "グローブ"]):    "クイックシルバー",
    frozenset(["涙",          "チョッキ"]):    "リデンプション",
    frozenset(["涙",          "ベルト"]):      "リデンプション",
    frozenset(["涙",          "クローク"]):    "パワーのチャリス",

    frozenset(["グローブ",    "グローブ"]):    "ティアマット",
    frozenset(["グローブ",    "チョッキ"]):    "ソーンメイル",
    frozenset(["グローブ",    "ベルト"]):      "ステラックの篭手（Crit）",
    frozenset(["グローブ",    "クローク"]):    "フローズンハート",

    frozenset(["チョッキ",    "チョッキ"]):    "ガーゴイル・ストーンプレート",
    frozenset(["チョッキ",    "ベルト"]):      "サンファイア・ケープ",
    frozenset(["チョッキ",    "クローク"]):    "ソーンメイル",

    frozenset(["ベルト",      "ベルト"]):      "ウォーモグのアーマー",
    frozenset(["ベルト",      "クローク"]):    "フローズンハート",

    frozenset(["クローク",    "クローク"]):    "ドラゴンクロウ",
}

# 完成アイテム → キーワードタグ（構成 item_keywords とのマッチに使う）
ITEM_TAGS: Dict[str, List[str]] = {
    "デスブレード":              ["BFソード", "剣", "AD", "Sword", "Deathblade"],
    "ギンソーのレイジブレード":  ["リカーブボウ", "BFソード", "弓", "AD", "AS", "攻撃速度", "ギンソー", "Rageblade"],
    "インフィニティ・エッジ":    ["BFソード", "剣", "クリティカル", "AD", "Crit", "インフィニティ", "Infinity"],
    "ブラッドサースター":        ["BFソード", "剣", "AD", "吸血", "Bloodthirster"],
    "ステラックの篭手":          ["BFソード", "剣", "AD", "HP", "Sterak"],
    "ヘクステック・ガンブレード":["BFソード", "剣", "涙", "AD", "AP", "Gunblade"],
    "クイックシルバー":          ["BFソード", "剣", "クローク", "AD", "Quicksilver"],
    "ナイトの縁":                ["BFソード", "剣", "ロッド", "AD", "AP"],
    "ラピッドファイア・キャノン":["リカーブボウ", "弓", "AS", "攻撃速度", "射程", "ラピッドファイア", "Rapidfire"],
    "ラスト・ウィスパー":        ["リカーブボウ", "弓", "AD", "Crit", "クリティカル", "ラスト・ウィスパー", "Last Whisper"],
    "サンファイア・ケープ":      ["チョッキ", "ベルト", "Tank", "タンク", "HP", "Sunfire"],
    "タイタンの決意":            ["リカーブボウ", "弓", "ベルト", "HP", "AS"],
    "ラバドンのデスキャップ":    ["ロッド", "AP", "魔力", "Rabadon", "デスキャップ"],
    "ブルーバフ":                ["ロッド", "涙", "AP", "マナ", "Blue Buff", "ブルーバフ"],
    "ジュエルド・ガントレット":  ["ロッド", "グローブ", "AP", "Crit", "クリティカル", "Jeweled Gauntlet", "ジュエルド"],
    "アイオニック・スパーク":    ["ロッド", "チョッキ", "AP", "Tank", "タンク"],
    "リデンプション":            ["涙", "ベルト", "回復", "HP", "Redemption"],
    "ドラゴンクロウ":            ["クローク", "チェーン", "Tank", "タンク", "MR", "Dragon's Claw", "ドラゴンクロウ"],
    "蒼者の穂先":                ["涙", "AP", "マナ", "蒼者", "Spear of Shojin"],
    "パワーのチャリス":          ["涙", "クローク", "AP", "MR", "チャリス"],
    "ガーゴイル・ストーンプレート":["チョッキ", "Tank", "タンク", "Armor", "鎧", "Gargoyle", "ガーゴイル"],
    "ウォーモグのアーマー":      ["ベルト", "Tank", "タンク", "HP", "Warmog", "ウォーモグ"],
    "ソーンメイル":              ["チョッキ", "クローク", "Tank", "タンク", "Armor", "Thornmail", "ソーンメイル"],
}


def _normalize(name: str) -> str:
    return ALIASES.get(name.strip().lower(), ALIASES.get(name.strip(), name.strip()))


def _load_augments() -> List[dict]:
    try:
        with open(_AUGMENTS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _load_comp_data(comp_id: str) -> Optional[dict]:
    try:
        with open(_COMPS_PATH, encoding="utf-8") as f:
            comps = json.load(f)
        return next((c for c in comps if c["id"] == comp_id), None)
    except Exception:
        return None


def _aug_tier_score(tier: str) -> int:
    return {"Prismatic": 30, "プリズマティック": 30,
            "Gold": 15, "ゴールド": 15,
            "Silver": 0, "シルバー": 0}.get(tier, 0)


def _is_augment_round(stage: str) -> bool:
    try:
        major, minor = stage.split("-")
        return (int(major), int(minor)) in {(2, 1), (3, 2), (4, 2)}
    except Exception:
        return False

def _is_gods_round(stage: str) -> bool:
    try:
        major, minor = stage.split("-")
        return (int(major), int(minor)) in {(2, 4), (3, 4), (4, 4)}
    except Exception:
        return False

def _is_god_boon_round(stage: str) -> bool:
    try:
        major, minor = stage.split("-")
        return (int(major), int(minor)) == (4, 7)
    except Exception:
        return False


# ---- Set17: 神データ（Realm of the Gods）----
GODS_DATA: Dict[str, dict] = {
    "アーリ": {
        "en": "Ahri",
        "traits": ["Fast Level", "Fast Roll", "経済", "Gold", "XP", "経験値", "リロール", "Fast 9"],
        "desc": "ゴールド・XP・リロール型。Fast Level/Rollすべての戦略に対応。経済重視の汎用神。",
        "boon": "経済オファリング（ゴールド・XP・リロール）",
        "hp_sensitive": False,
    },
    "オーレリオン・ソル": {
        "en": "Aurelion Sol",
        "traits": ["Mecha", "メカ", "Anima", "アニマ", "Primordians", "プリモーディアン", "クエスト"],
        "desc": "クエスト報酬型。AP+AD・アイテム・トレイト+1などクエスト達成で強力な報酬。メカ/アニマ構成と相性◎",
        "boon": "クエスト達成報酬（AP/AD強化・アイテム・トレイト+1）",
        "hp_sensitive": False,
    },
    "エコー": {
        "en": "Ekko",
        "traits": ["LooseStreak", "負けストリーク", "Anima", "アニマ", "スケール", "Scaling"],
        "desc": "スケーリング報酬型。数ラウンド後に効果発動。負けストリーク/後半スケール戦略と相性◎",
        "boon": "遅延スケーリング報酬（複数ラウンド後に発動）",
        "hp_sensitive": False,
    },
    "イブリン": {
        "en": "Evelynn",
        "traits": ["WinStreak", "連勝", "Rogue", "ローグ", "Assassin", "アサシン", "バースト"],
        "desc": "ハイリスク・ハイリターン型。HP消費で高価値報酬（ゴールド・チャンピオンアップグレード・エンブレム）。連勝中のみ推奨。",
        "boon": "HP消費型高価値報酬（金・アップグレード・エンブレム）",
        "hp_sensitive": True,  # HP高い時のみ有効
    },
    "ケイル": {
        "en": "Kayle",
        "traits": ["Stargazer", "スターゲイザー", "Fast9", "後期", "Scaling", "アイテム", "コンポーネント", "BIS"],
        "desc": "コンポーネント豊富型。マルチキャリーやBISアイテム構築に最適。スターゲイザー・Fast9と相性◎",
        "boon": "コンポーネント・アイテム豊富（BISアイテム構築向け）",
        "hp_sensitive": False,
    },
    "ソラカ": {
        "en": "Soraka",
        "traits": ["Shepherd", "シェパード", "Anima", "アニマ", "LooseStreak", "負けストリーク", "回復", "HP"],
        "desc": "HP回復+ゴールド型。負けストリーク向け。各ステージでHP回復+ゴールド提供。アニマ/シェパードと相性◎",
        "boon": "HP回復＋ゴールド（負けストリーク向けキャッチアップ）",
        "hp_sensitive": False,
    },
    "スレッシュ": {
        "en": "Thresh",
        "traits": [],  # ランダム — 構成不問
        "desc": "完全ランダム型。毎ステージ異なる神の報酬を獲得。ギャンブル向け。構成の縛りなし。",
        "boon": "ランダム神のBoon（各ステージで異なる神の報酬）",
        "hp_sensitive": False,
    },
    "ヴァルス": {
        "en": "Varus",
        "traits": ["Reroll", "リロール", "Dark Star", "ダークスター", "Sniper", "スナイパー", "低コスト"],
        "desc": "リロール特化型。ユニット・デュプリケーター・ゴールド提供。低コストリロール構成と相性◎",
        "boon": "ユニット＋デュプリケーター＋ゴールド（リロール向け）",
        "hp_sensitive": False,
    },
    "ヤスオ": {
        "en": "Yasuo",
        "traits": [],  # ヘックスバフ — 全構成対応
        "desc": "ヘックスバフ型。トレイト別に異なるバフヘックス（Socialite=Mana再生、Wind=攻撃速度等）。ほぼ全構成対応。",
        "boon": "トレイト固有ヘックスバフ（Mana再生・攻撃速度等）",
        "hp_sensitive": False,
    },
    "ペング": {
        "en": "Pengu",
        "traits": [],
        "desc": "HP依存の汎用報酬。順位が低いほど良いオファリング。HP30以下で特に強力。コンポーネント付き。",
        "boon": "HP依存汎用報酬（全オファリングにコンポーネント付き）",
        "hp_sensitive": True,  # HP低い時に強い
    },
}

# God Boon カテゴリ → 評価キーワード
BOON_KEYWORDS: Dict[str, List[str]] = {
    "Combat":   ["強化", "攻撃", "戦闘", "ダメージ", "combat", "attack", "power", "offensive", "AD", "AP"],
    "Economy":  ["ゴールド", "経済", "インタレスト", "Gold", "Economy", "interest", "ゴールド生成"],
    "Utility":  ["経験値", "レベル", "XP", "exp", "level", "ユーティリティ", "utility", "ヘックス"],
    "Healing":  ["回復", "HP", "ヒール", "heal", "shield", "シールド", "タクティシャン"],
    "Items":    ["アイテム", "素材", "コンポーネント", "item", "component", "forge", "デュプリケーター"],
}


# ---- Public API ----

def calc_augment_choice(choices: List[str], comp_id: str = "", stage: str = "1-1") -> dict:
    """
    3択オーグメントのうちどれを選ぶか。
    Returns {"recommended": str, "ranked": [{"name","score","reason"}]}
    """
    aug_db = {a["name"]: a for a in _load_augments()}
    comp = _load_comp_data(comp_id)
    aug_keywords: List[str] = comp.get("augment_keywords", []) if comp else []

    economy_kw = ["経済", "Gold", "Economy", "後期", "Fast 9", "リロール",
                  "スプーン", "パンドラ", "大勝利", "忍耐", "ローリング"]

    # 2-1 は経済ボーナス高め
    try:
        major, minor = stage.split("-")
        eco_weight = 1.5 if int(major) <= 2 else 1.0
    except Exception:
        eco_weight = 1.0

    ranked = []
    for choice in choices:
        aug_info = aug_db.get(choice, {})
        tier = aug_info.get("tier", "Silver")
        keywords = aug_info.get("keywords", [])
        desc = aug_info.get("desc", "")

        score = _aug_tier_score(tier)
        reasons = []

        kw_match = sum(
            1 for k in aug_keywords
            if any(k.lower() in kw.lower() or kw.lower() in k.lower() for kw in keywords)
        )
        if kw_match:
            score += kw_match * 20
            reasons.append("構成シナジー◎")

        eco_match = any(
            ek.lower() in kw.lower() or kw.lower() in ek.lower()
            for ek in economy_kw for kw in keywords
        )
        if eco_match:
            score += int(15 * eco_weight)
            reasons.append("経済オーグメント" + ("（序盤特にGood）" if eco_weight > 1 else ""))

        tier_ja = {"Silver": "シルバー", "Gold": "ゴールド",
                   "Prismatic": "プリズマティック"}.get(tier, tier)
        reasons.append(tier_ja)
        if desc:
            reasons.append(desc[:35])

        ranked.append({"name": choice, "score": score, "reason": " / ".join(reasons)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (choices[0] if choices else ""),
        "ranked": ranked,
    }


def calc_forge_choice(choices: List[str], held_items: List[str] = None, comp_id: str = "") -> dict:
    """
    フォージで提示されたコンポーネントのうちどれを取るか。
    Returns {"recommended": str, "ranked": [{"name","score","reason","builds"}]}
    """
    comp = _load_comp_data(comp_id)
    item_kw: List[str] = comp.get("item_keywords", []) if comp else []

    held_norm = [_normalize(h) for h in (held_items or [])]

    ranked = []
    for raw_name in choices:
        norm = _normalize(raw_name)
        display = COMPONENT_DISPLAY.get(norm, raw_name)
        score = 0
        reasons: List[str] = []
        builds: List[str] = []

        # コンポーネント自体のキーワードマッチ
        direct = sum(1 for k in item_kw
                     if k.lower() in norm.lower() or norm.lower() in k.lower()
                     or k.lower() in raw_name.lower())
        if direct:
            score += direct * 8
            reasons.append("構成素材")

        # 保有素材との組み合わせ → 完成アイテム評価
        partners = held_norm if held_norm else [norm]
        for partner in partners:
            key = frozenset([norm, partner])
            full = COMBOS.get(key)
            if full:
                builds.append(full)
                tags = ITEM_TAGS.get(full, [])
                m = sum(1 for k in item_kw
                        if any(k.lower() in t.lower() or t.lower() in k.lower() for t in tags))
                if m:
                    score += m * 15
                    reasons.append(f"→ {full}")

        if score == 0:
            reasons.append("構成に直接関係なし")

        ranked.append({
            "name": display,
            "score": score,
            "reason": " / ".join(dict.fromkeys(reasons)) if reasons else "汎用素材",
            "builds": list(dict.fromkeys(builds)),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (choices[0] if choices else ""),
        "ranked": ranked,
    }


# ---- 状況アドバイス ----

def calc_situation_actions(state, comp_id: str = "") -> List[dict]:
    """
    現在の状況に応じて「今やるべきこと」を優先度付きで返す。
    Returns List[{"priority": "urgent"|"high"|"medium", "action": str, "detail": str}]
    """
    actions: List[dict] = []
    stage  = getattr(state, "stage", "1-1")
    hp     = getattr(state, "hp", 100)
    gold   = getattr(state, "gold", 0)
    level  = getattr(state, "level", 1)
    streak = getattr(state, "streak", 0)
    board  = getattr(state, "board", [])
    items_held = getattr(state, "items", [])

    try:
        major_s, minor_s = stage.split("-")
        major, minor = int(major_s), int(minor_s)
    except Exception:
        major, minor = 1, 1

    comp       = _load_comp_data(comp_id)
    min_level  = comp.get("min_level", 7) if comp else 7
    comp_name  = comp.get("name", "") if comp else ""
    play_style = comp.get("play_style", "") if comp else ""
    board_size = len(board)
    board_names = {u.name for u in board} if board else set()

    # ── 緊急: HP 低下 ──
    if hp <= 20:
        actions.append({
            "priority": "urgent",
            "action": "盤面を即強化 — 負けると脱落",
            "detail": f"HP {hp}。ゴールドを全放出してでも強いユニットを買ってロールする。",
        })
    elif hp <= 40:
        actions.append({
            "priority": "urgent",
            "action": "ロールして戦闘力を上げる",
            "detail": f"HP {hp} — 危険域。あと2〜3敗で脱落圏。前衛を最低2体確保してから守りに入る。",
        })

    # ── 特殊ラウンド（優先表示）──
    if _is_augment_round(stage):
        actions.append({
            "priority": "urgent",
            "action": f"オーグメントを選ぶ（{stage}）",
            "detail": "自動でオーグメント選択ウィンドウが開きます。3択の中から最適案を確認。",
        })
    if _is_gods_round(stage):
        actions.append({
            "priority": "urgent",
            "action": f"神のオファリングを選ぶ（{stage}）",
            "detail": "同じ神を2回選ぶと神アラインが確定。構成との相性を神選択ツールで確認。",
        })
    if _is_god_boon_round(stage):
        actions.append({
            "priority": "urgent",
            "action": "God Boon を選ぶ（4-7）",
            "detail": "アーモリーから大型報酬を1つ選択。神アラインと構成に合ったBoonを優先。",
        })

    # ── 盤面配置: 今レベルで何を出してどこに置くか ──
    comp_units = comp.get("units", []) if comp else []
    carry_name = comp.get("carry", "") if comp else ""

    if comp_units:
        # レベル分のスロットに入れるユニットを選択
        ideal = comp_units[:level]
        front_board = [u["name"] for u in ideal if u.get("position") == "frontline"]
        back_board  = [u["name"] for u in ideal if u.get("position") != "frontline"]

        # 前衛が0体なら最初の frontline ユニットをスワップ
        if not front_board:
            all_fl = [u["name"] for u in comp_units if u.get("position") == "frontline"]
            if all_fl:
                front_board = [all_fl[0]]
                back_board = back_board[:-1] if back_board else back_board

        bench_now = [u["name"] for u in comp_units[level:level + 2]]

        parts = []
        if back_board:
            parts.append(f"後列: {'・'.join(back_board)}")
        if front_board:
            parts.append(f"前列: {'・'.join(front_board)}")

        detail_carry = f"{carry_name}を後列右端〜中央に固定。" if carry_name else ""
        detail_bench = f"ベンチ待機: {'・'.join(bench_now)}" if bench_now else ""

        actions.append({
            "priority": "high",
            "action": f"Lv{level}盤面: {' / '.join(parts)}",
            "detail": detail_carry + detail_bench,
        })

    # ── 探すべきキーユニット ──
    key_units = [u["name"] for u in comp_units if u.get("stars", 2) >= 2]
    missing_keys = [u for u in key_units if u not in board_names][:3]
    if missing_keys:
        actions.append({
            "priority": "high",
            "action": f"ショップで探す: {'・'.join(missing_keys)}",
            "detail": f"出たら即買い。[D]でリロール。{comp_name}のコアユニット。",
        })
    elif key_units:
        actions.append({
            "priority": "high",
            "action": f"{'・'.join(key_units[:2])} を2つ星に",
            "detail": "同名ユニットをあと1〜2枚引いて2つ星へ。ショップを流して引きを待つ。",
        })

    # ── レベル・ロール判断（常に1つ表示）──
    if "Fast 9" in play_style or "fast9" in comp_id:
        if level < 9:
            actions.append({
                "priority": "high",
                "action": f"[E]でLv{level}→9へ経験値購入を続ける",
                "detail": "Fast9はGold50をキープしながら毎ラウンドEを押してLv9を目指す。ロールはしない。",
            })
        else:
            actions.append({
                "priority": "high",
                "action": "Lv9でロール — 高コストユニットを引く",
                "detail": "Lv9ならコスト4・5のユニット出現率UP。50g貯まるまで待たずロール開始してOK。",
            })
    elif "リロール" in play_style:
        if level < min_level:
            actions.append({
                "priority": "high",
                "action": f"[E]でLv{min_level}まで経験値購入（あと{min_level - level}回）",
                "detail": f"リロール構成はLv{min_level}に到達してから一気にロールする。今はEキーを押す。",
            })
        else:
            actions.append({
                "priority": "high",
                "action": f"Lv{min_level}でリロール — 3つ星を目指す",
                "detail": "[D]キーでショップを流す。30g以下になったら一旦止めて次のラウンドのゴールドを待つ。",
            })
    else:
        # 通常後期ロール構成
        if level < min_level:
            actions.append({
                "priority": "high",
                "action": f"[E]でLv{min_level}へ（あと{min_level - level}回）",
                "detail": f"{comp_name}の完成にはLv{min_level}必要。4gずつ[E]を押してレベルアップ。",
            })
        elif major >= 3:
            actions.append({
                "priority": "high",
                "action": f"Lv{level}でロールして{comp_name}を完成させる",
                "detail": "[D]キーでリロール。20〜30g使ってキーユニットを揃えたら一旦止めてゴールドを貯める。",
            })
        else:
            # 序盤（ステージ1〜2）
            early = comp.get("early_board", []) if comp else []
            if early:
                missing_early = [u for u in early if u not in board_names][:3]
                if missing_early:
                    actions.append({
                        "priority": "medium",
                        "action": f"序盤盤面を固める: {'・'.join(missing_early)} を狙う",
                        "detail": f"{comp_name}の序盤ボード。強い盤面でラウンドをこなしながらゴールドを貯める。",
                    })
                else:
                    actions.append({
                        "priority": "medium",
                        "action": "序盤盤面が整っています — ゴールドを貯める",
                        "detail": "序盤ボードOK。ロールせずインタレスト（10g毎+1g）を積んで中盤に備える。",
                    })

    # ── 連勝/連敗ストリーク維持 ──
    if streak >= 3:
        actions.append({
            "priority": "medium",
            "action": f"{streak}連勝中 — 盤面を変えない",
            "detail": "ストリーク維持が重要。必要でないロールや売却は避けてボーナスを守る。",
        })
    elif streak <= -3:
        actions.append({
            "priority": "medium",
            "action": f"{abs(streak)}連敗中 — 連敗ボーナスを活用",
            "detail": "連敗ボーナスゴールドが加算されている。HPが許す限り意図的に負けてゴールドを貯める戦略も有効。",
        })

    # ── アイテム未装備 ──
    if len(items_held) >= 2:
        actions.append({
            "priority": "medium",
            "action": f"素材アイテム{len(items_held)}個をキャリーに装備",
            "detail": "アイテム未装備は戦闘力ロス。金床ツールで最適な完成アイテムを確認して装備。",
        })

    # ── 優先度ソート・重複除去 ──
    priority_order = {"urgent": 0, "high": 1, "medium": 2}
    actions.sort(key=lambda x: priority_order.get(x["priority"], 3))

    return actions[:6]


def calc_gods_choice(
    gods_offered: List[str],
    comp_id: str = "",
    god_align: str = "",
    hp: int = 100,
) -> dict:
    """
    Realm of the Gods で提示された神のうちどれを選ぶか。
    Returns {"recommended": str, "ranked": [{"name","score","reason"}]}
    """
    comp = _load_comp_data(comp_id)
    comp_affinities: List[str] = comp.get("god_affinities", []) if comp else []
    comp_tags: List[str] = (comp.get("key_tags", []) + comp.get("traits", [])) if comp else []
    play_style: str = comp.get("play_style", "") if comp else ""

    # Pengu は常に候補に加える
    candidates = list(gods_offered)
    if "ペング" not in candidates:
        candidates.append("ペング")

    ranked = []
    for god_name in candidates:
        god = GODS_DATA.get(god_name)
        if not god:
            ranked.append({"name": god_name, "score": 0, "reason": "不明な神"})
            continue

        score = 0
        reasons: List[str] = []

        # 構成アフィニティの直接マッチ
        if god_name in comp_affinities:
            score += 40
            reasons.append("構成との相性◎")

        # traitキーワードマッチ
        trait_match = sum(
            1 for t in god.get("traits", [])
            if any(t.lower() in ct.lower() or ct.lower() in t.lower() for ct in comp_tags + [play_style])
        )
        if trait_match:
            score += trait_match * 15
            reasons.append(f"トレイト一致({trait_match})")

        # 神アライン継続ボーナス
        if god_align and god_name == god_align:
            score += 25
            reasons.append("アライン継続ボーナス")

        # HP依存スコア
        if god.get("hp_sensitive"):
            if god_name == "ペング":
                # ペングはHP低いほど強い
                pengu_bonus = max(0, (60 - hp) // 2)
                if hp <= 30:
                    score += 30 + pengu_bonus
                    reasons.append(f"HP{hp}でペング強力")
                elif hp <= 50:
                    score += 15 + pengu_bonus
                    reasons.append(f"HP{hp}でペング有効")
            elif god_name == "イブリン":
                # イブリンはHP高いほど安全
                if hp >= 70:
                    score += 20
                    reasons.append("HP十分でリスク許容")
                else:
                    score -= 10
                    reasons.append(f"HP{hp}でリスク高（HP消費）")

        # ベーススコア
        if not reasons:
            score += 5
            reasons.append("汎用オファリング")

        reasons.append(god.get("desc", "")[:35])
        ranked.append({"name": god_name, "score": max(0, score), "reason": " / ".join(reasons)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (candidates[0] if candidates else ""),
        "ranked": ranked,
    }


def calc_god_boon(
    boons_offered: List[str],
    comp_id: str = "",
    god_align: str = "",
) -> dict:
    """
    God Boon（ステージ4-7）の選択アドバイス。
    Returns {"recommended": str, "ranked": [{"name","score","reason"}]}
    """
    comp = _load_comp_data(comp_id)
    comp_tags: List[str] = (
        comp.get("key_tags", []) + comp.get("traits", []) + comp.get("item_keywords", [])
    ) if comp else []
    play_style: str = comp.get("play_style", "") if comp else ""

    # アライン神のBoon傾向
    aligned_god = GODS_DATA.get(god_align, {})
    aligned_boon_hint: str = aligned_god.get("boon", "")

    ranked = []
    for boon in boons_offered:
        score = 0
        reasons: List[str] = []
        boon_lower = boon.lower()

        # アライン神のBoonヒントとのマッチ
        if aligned_boon_hint and any(w in boon_lower for w in aligned_boon_hint.lower().split("（")[0].split("・")):
            score += 30
            reasons.append(f"アライン神({god_align})のBoon")

        # カテゴリキーワードマッチ
        for cat, kws in BOON_KEYWORDS.items():
            m = sum(1 for kw in kws if kw.lower() in boon_lower)
            if m:
                score += m * 10

                # 構成との相性
                comp_match = sum(
                    1 for ct in comp_tags
                    if any(kw.lower() in ct.lower() or ct.lower() in kw.lower() for kw in kws)
                )
                if comp_match:
                    score += comp_match * 8
                    reasons.append(f"{cat}ボーン(構成マッチ)")
                else:
                    reasons.append(f"{cat}ボーン")

        # Fast9/リロールの経済Boon優遇
        eco_kws = ["Gold", "ゴールド", "経済", "XP", "経験値"]
        if any(ek in play_style for ek in ["Fast 9", "リロール"]):
            if any(ek.lower() in boon_lower for ek in eco_kws):
                score += 15
                reasons.append("戦略との経済シナジー")

        if not reasons:
            score = 5
            reasons.append("汎用Boon")

        ranked.append({"name": boon, "score": score, "reason": " / ".join(dict.fromkeys(reasons))})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {
        "recommended": ranked[0]["name"] if ranked else (boons_offered[0] if boons_offered else ""),
        "ranked": ranked,
    }
