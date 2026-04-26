import React, { useCallback, useEffect, useRef, useState } from "react";

import type { GodsChoiceResponse } from "../types";
import { adviseGods } from "../api/advise";
import { writeOverlayContext } from "../utils/analyzeState";

const GOD_PALETTE = ["#f9a8d4", "#818cf8", "#67e8f9", "#f472b6", "#fde68a", "#86efac", "#fb923c", "#60a5fa", "#a3e635"];

function colorForName(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  return GOD_PALETTE[hash % GOD_PALETTE.length];
}

interface Props {
  compId?: string;
  godAlign?: string;
  hp?: number;
  offeredGods?: string[];
}

export function GodsPicker({ compId = "", godAlign = "", hp = 100, offeredGods = [] }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [align, setAlign] = useState(godAlign);
  const [result, setResult] = useState<GodsChoiceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastAutoSignatureRef = useRef("");
  const availableGods = Array.from(
    new Set([
      ...offeredGods.map((name) => name.trim()).filter(Boolean),
      ...(align ? [align] : []),
      ...((result?.ranked ?? []).map((item) => item.name)),
      ...Array.from(selected),
    ]),
  );

  useEffect(() => {
    setAlign(godAlign);
  }, [godAlign]);

  const runAdvice = useCallback(async (choices: string[]) => {
    if (choices.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await adviseGods(choices, compId, align, hp);
      setResult(res);
      if (res.recommended) {
        writeOverlayContext({ godAlign: res.recommended });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to analyze gods");
    } finally {
      setLoading(false);
    }
  }, [align, compId, hp]);

  useEffect(() => {
    const normalized = offeredGods.map((name) => name.trim()).filter(Boolean);
    if (normalized.length === 0) return;

    setSelected(new Set(normalized));

    const signature = JSON.stringify({ normalized, compId, align, hp });
    if (signature !== lastAutoSignatureRef.current) {
      lastAutoSignatureRef.current = signature;
      void runAdvice(normalized);
    }
  }, [align, compId, hp, offeredGods, runAdvice]);

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else if (next.size < 2) {
        next.add(name);
      }
      return next;
    });
  };

  const handleSubmit = useCallback(async () => {
    await runAdvice([...selected]);
  }, [runAdvice, selected]);

  return (
    <div className="picker-card">
      <div className="picker-title">God Selection</div>
      <p className="picker-hint">Pick the offered gods or let the popup auto-fill them.</p>

      <div className="gods-grid">
        {availableGods.map((god) => (
          <button
            key={god}
            className={`god-chip ${selected.has(god) ? "selected" : ""}`}
            style={{ "--god-color": colorForName(god) } as React.CSSProperties}
            onClick={() => toggle(god)}
            title={god}
          >
            {god}
          </button>
        ))}
      </div>

      <div className="picker-align-row">
        <label className="picker-align-label">Current alignment</label>
        <select className="picker-align-select" value={align} onChange={(e) => setAlign(e.target.value)}>
          <option value="">None</option>
          {availableGods.map((god) => (
            <option key={god} value={god}>
              {god}
            </option>
          ))}
        </select>
      </div>

      <button className="picker-btn" onClick={handleSubmit} disabled={selected.size === 0 || loading}>
        {loading ? "Analyzing..." : "Recommend"}
      </button>

      {error && <p className="picker-error">{error}</p>}

      {result && (
        <div className="picker-result">
          <div className="picker-recommended">
            <span className="pick-label">Best</span>
            <span className="pick-name" style={{ color: colorForName(result.recommended) }}>
              {result.recommended}
            </span>
          </div>
          <ol className="picker-rank-list">
            {result.ranked.map((rank, i) => (
              <li key={i} className={`picker-rank-item ${i === 0 ? "rank-best" : ""}`}>
                <span className="rank-num">#{i + 1}</span>
                <span className="rank-name" style={{ color: colorForName(rank.name) }}>
                  {rank.name}
                </span>
                <span className="rank-score">{rank.score}pt</span>
                <span className="rank-reason">{rank.reason}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
