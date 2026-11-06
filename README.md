# TFT Advisor MVP

## ソースコードの制作方法（生成AI利用の明示）

**このリポジトリで公開しているソースコードの記述・修正（コーディング）は、すべて生成AIが担当しました。本人が手書きで実装したコードとして提示するものではありません。**

本人はテーマの選定、目的・要件の整理、AIへの指示、動作確認、結果の読み取り、改善方針の判断などに関わっています。ただし、担当した内容・検証済みの範囲はプロジェクトごとに異なります。学習時に取り組んだ演習と、GitHubで公開しているコードの制作方法は分けて説明します。

このリポジトリは、手書きのコーディング能力の証明ではなく、**生成AIを活用した開発、要件整理、検証・評価、改善の取り組み**を示す成果物です。


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


## セキュリティ設定（2026-11-04）

- バックエンドは `backend/run.bat` で `127.0.0.1:8010` のみ待受します。LAN/インターネットへポートを公開しないでください。
- CORS と Host 検証を追加し、標準では `http://127.0.0.1:5173` / `http://localhost:5173` とループバックUI（8010番）のみ許可します。ブラウザの不審なOriginからのリクエストは403で拒否します。
- カスタムポートを使う場合は、起動前に `TFT_ALLOWED_ORIGINS` に**信頼できる正確なOrigin**をカンマ区切りで設定してください。例：`http://127.0.0.1:5174`。ワイルドカードは設定しないでください。
- `file://` / Overwolfの拡張ページが `Origin: null` を送信する構成では、既定で通信を拒否します。どうしても必要な場合に限り、**信頼できるローカル環境だけ**で `TFT_ALLOW_OPAQUE_ORIGIN=1` を設定してからバックエンドを起動してください。これにより他の不透明なOriginも区別できなくなるため、通常は無効のままにしてください。
- フロントエンドの `?apiBase=` に外部URLを指定しても採用されません。ゲーム情報や画面データの外部送信を防止するための制限です。
- 更新したPython依存関係は `cd backend && python -m pip install -r requirements.txt` で反映してください。FastAPI・Pydantic・Requestsも合わせて更新し、Pillowは脆弱性対応版（13.0.0）です。
- Electronのサポート対象版へのアップグレードは別途Windows UI検証が必要です。パッケージ更新時はNode.js 22.12以降を使い、`overlay_app` で `npm ci` を実行してください。

コードを変更しただけでは、起動中のローカルアプリに反映されません。依存更新後にバックエンド・フロントエンド・オーバーレイを再起動してください。
