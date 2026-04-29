# TFT Advisor MVP

TFT（Teamfight Tactics）の対戦中に盤面情報を手入力すると、次の行動を即時提案するWebアプリです。

---

## フォルダ構成

```
TFT/
├── README.md
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py          # FastAPI エントリポイント
│       ├── schemas.py       # リクエスト / レスポンス型定義
│       ├── logic/
│       │   ├── scoring.py   # boardStrength 計算
│       │   ├── economy.py   # economyPlan 判定
│       │   └── comps.py     # 構成マッチングスコア
│       └── data/
│           └── current/     # ← セット更新時はここを差し替え
│               ├── champions.json
│               ├── traits.json
│               ├── items.json
│               ├── augments.json
│               └── comps.json
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── App.tsx
        ├── App.css
        ├── main.tsx
        ├── types/index.ts   # 型定義
        ├── api/analyze.ts   # API呼び出し
        └── components/
            ├── InputPanel.tsx
            ├── ResultPanel.tsx
            └── UnitListInput.tsx
```

Windows helper scripts are organized under `scripts/windows/`.

---

## セットアップ

### 前提条件

| ツール | バージョン目安 |
|---|---|
| Python | 3.10 以上 |
| Node.js | 18 以上 |
| npm | 9 以上 |

---

## バックエンド起動

```bash
cd backend
.\run.bat
```

起動後 http://127.0.0.1:8010/docs で Swagger UI が確認できます。

---

## フロントエンド起動

別ターミナルで：

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 でアプリが開きます。

---

## 動作確認手順

1. バックエンドを起動（ポート 8010）
2. フロントエンドを起動（ポート 5173）
3. ブラウザで http://localhost:5173 を開く
4. **「サンプルを読み込む」** ボタンを押す
5. **「Analyze」** ボタンを押す
6. 右側に分析結果が表示される

---

## サンプル入力例（curl）

```bash
curl -X POST http://127.0.0.1:8010/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "patch": "current-ranked",
    "stage": "3-2",
    "level": 6,
    "hp": 82,
    "gold": 34,
    "streak": 3,
    "board": [
      {"name": "Front Tank",   "stars": 2, "tags": ["Guardian", "Tank", "Frontline"]},
      {"name": "AP Carry",     "stars": 2, "tags": ["Mage", "Carry", "Arcanist"]},
      {"name": "Invoker Unit", "stars": 1, "tags": ["Invoker", "Mage"]}
    ],
    "bench": [],
    "shop": [
      {"name": "AP Carry",   "stars": 1, "tags": ["Mage", "Carry", "Arcanist"]},
      {"name": "Tank Bonus", "stars": 1, "tags": ["Guardian", "Tank", "Frontline"]}
    ],
    "items": ["Rod", "Tear", "Vest", "Belt"],
    "augments": ["Economy Augment", "AP Augment"],
    "notes": "AP素材多め。前衛不足。"
  }'
```

---

## データ差し替え方法（セット更新時）

`backend/app/data/current/` 以下のJSONを差し替えるだけで新セットに対応できます。

### comps.json（構成定義）

```json
[
  {
    "id":                "your_comp_id",
    "name":              "表示名",
    "key_tags":          ["Mage", "Carry"],    // 後衛・シナジータグ
    "frontline_tags":    ["Tank", "Guardian"], // 前衛タグ
    "item_keywords":     ["Rod", "Tear"],      // アイテム素材のキーワード
    "augment_keywords":  ["AP", "Mage"],       // オーグメント名のキーワード
    "min_level":         7,                    // 構成が完成するレベル
    "description":       "構成の説明"
  }
]
```

### champions.json（チャンピオン定義）

```json
[
  {
    "name":   "Ahri",
    "cost":   4,
    "traits": ["Mage", "Invoker"],
    "tags":   ["Mage", "Carry", "Invoker"]
  }
]
```

### ポイント

- `tags` は評価ロジックで使われるラベルです。新セットのシナジー名をそのまま入れてください。
- `key_tags` / `frontline_tags` に一致するユニットが多いほど構成スコアが上がります。
- `item_keywords` は部分一致で判定されます（例: `"Rod"` は `"Needlessly Large Rod"` にも一致）。

---

## API仕様

### POST /analyze

**リクエスト**

| フィールド | 型 | 説明 |
|---|---|---|
| stage | string | 例: "3-2" |
| level | int | 現在のレベル |
| hp | int | 現在のHP |
| gold | int | 所持Gold |
| streak | int | 連勝/連敗数 |
| board | Unit[] | 盤面ユニット |
| bench | Unit[] | ベンチユニット |
| shop | Unit[] | ショップ5枠 |
| items | string[] | 所持素材名 |
| augments | string[] | オーグメント名 |
| notes | string | 自由メモ |

**Unit型**

```json
{ "name": "string", "stars": 1, "tags": ["string"] }
```

**レスポンス**

| フィールド | 説明 |
|---|---|
| boardStrength | 盤面強度スコア（0〜100） |
| topComp | 推奨構成（id, name, score, reason） |
| economyPlan | 経済行動（action, reason） |
| shopRecommendations | ショップ購入優先順位 |
| cutCandidates | 切り推奨ユニット |
| itemPlan | アイテム方針テキスト |
| nextImprovements | 次に足すべき要素リスト |

---

## 今後の拡張候補

### 近期
- **実名データ投入**: `champions.json` に現行セットの実チャンピオンデータを追加
- **構成候補の拡充**: `comps.json` に現行メタ構成（5〜10種）を追加

### 中期
- **スクリーンショット認識**: OpenCV でゲーム画面から盤面を自動検出
  - 入力フォームと同じ `Unit[]` 形式に変換して `/analyze` に渡す設計なので追加しやすい
- **OCR**: Tesseract / PaddleOCR でユニット名・レベルを読み取り

### 長期
- **オーバーレイ表示**: Electron or OBS Browser Source でゲーム画面上に重ねて表示
- **パッチ更新対応**: `data/` フォルダを `data/set14.1/` のようにバージョン管理し、APIの `patch` パラメータで切り替え
- **統計ベース評価**: Riot APIからランク上位プレイヤーの構成データを収集してロジックを強化
- **モバイルアプリ**: React Native でスマホから手入力できるクライアントを作成
