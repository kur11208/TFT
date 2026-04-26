import React from "react";
import type { AnalyzeRequest } from "../types";
import { UnitListInput } from "./UnitListInput";

interface Props {
  request: AnalyzeRequest;
  onChange: (req: AnalyzeRequest) => void;
  onAnalyze: () => void;
  onLoadSample: () => void;
  loading: boolean;
}

export function InputPanel({ request, onChange, onAnalyze, onLoadSample, loading }: Props) {
  const set = <K extends keyof AnalyzeRequest>(key: K, value: AnalyzeRequest[K]) => {
    onChange({ ...request, [key]: value });
  };

  const setNum = (key: keyof AnalyzeRequest, raw: string) => {
    const value = parseInt(raw, 10);
    if (!Number.isNaN(value)) {
      set(key, value as AnalyzeRequest[typeof key]);
    }
  };

  const setCSV = (key: keyof AnalyzeRequest, raw: string) => {
    const values = raw.split(",").map((s) => s.trim()).filter(Boolean);
    set(key, values as AnalyzeRequest[typeof key]);
  };

  return (
    <div className="input-panel">
      <div className="panel-header">
        <h2>盤面入力</h2>
        <button type="button" className="btn-sample" onClick={onLoadSample}>
          サンプルを読み込む
        </button>
      </div>

      <section className="form-section">
        <h3>基本情報</h3>
        <div className="grid-2">
          <label>
            <span>ステージ</span>
            <input
              type="text"
              value={request.stage}
              placeholder="例: 3-2"
              onChange={(e) => set("stage", e.target.value)}
            />
          </label>
          <label>
            <span>レベル</span>
            <input
              type="number"
              min={1}
              max={10}
              value={request.level}
              onChange={(e) => setNum("level", e.target.value)}
            />
          </label>
          <label>
            <span>HP</span>
            <input
              type="number"
              min={0}
              max={100}
              value={request.hp}
              onChange={(e) => setNum("hp", e.target.value)}
            />
          </label>
          <label>
            <span>Gold</span>
            <input
              type="number"
              min={0}
              value={request.gold}
              onChange={(e) => setNum("gold", e.target.value)}
            />
          </label>
          <label>
            <span>ストリーク</span>
            <input
              type="number"
              value={request.streak}
              onChange={(e) => setNum("streak", e.target.value)}
            />
          </label>
        </div>
      </section>

      <section className="form-section">
        <h3>盤面</h3>
        <UnitListInput label="" units={request.board} onChange={(units) => set("board", units)} />
      </section>

      <section className="form-section">
        <h3>ベンチ</h3>
        <UnitListInput label="" units={request.bench} onChange={(units) => set("bench", units)} />
      </section>

      <section className="form-section">
        <h3>ショップ</h3>
        <UnitListInput label="" units={request.shop} onChange={(units) => set("shop", units)} />
      </section>

      <section className="form-section">
        <h3>アイテム / オーグメント</h3>
        <label>
          <span>保持アイテム素材</span>
          <input
            type="text"
            value={request.items.join(", ")}
            placeholder="例: Rod, Tear, Vest, Belt"
            onChange={(e) => setCSV("items", e.target.value)}
          />
        </label>
        <label>
          <span>取得済みオーグメント</span>
          <input
            type="text"
            value={request.augments.join(", ")}
            placeholder="例: Economy Augment, AP Augment"
            onChange={(e) => setCSV("augments", e.target.value)}
          />
        </label>
      </section>

      <section className="form-section">
        <h3>メモ</h3>
        <textarea
          rows={3}
          value={request.notes}
          placeholder="自由メモ。狙っている構成や盤面の悩みを書く。"
          onChange={(e) => set("notes", e.target.value)}
        />
      </section>

      <button type="button" className="btn-analyze" onClick={onAnalyze} disabled={loading}>
        {loading ? "分析中..." : "Analyze"}
      </button>
    </div>
  );
}
