import React, { useCallback, useEffect, useRef, useState } from "react";

import type { GodBoonResponse } from "../types";
import { adviseGodBoon } from "../api/advise";

interface Props {
  compId?: string;
  godAlign?: string;
  prefilledBoons?: string[];
}

function normalizeBoons(values: string[], length = 3): string[] {
  const next = values.map((value) => value.trim()).filter(Boolean).slice(0, length);
  while (next.length < length) next.push("");
  return next;
}

export function GodBoonPicker({ compId = "", godAlign = "", prefilledBoons = [] }: Props) {
  const [boons, setBoons] = useState(["", "", ""]);
  const [align, setAlign] = useState(godAlign);
  const [result, setResult] = useState<GodBoonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastAutoSignatureRef = useRef("");

  useEffect(() => {
    setAlign(godAlign);
  }, [godAlign]);

  const runAdvice = useCallback(async (nextBoons: string[]) => {
    if (nextBoons.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await adviseGodBoon(nextBoons, compId, align);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to analyze god boon");
    } finally {
      setLoading(false);
    }
  }, [align, compId]);

  useEffect(() => {
    const filled = prefilledBoons.map((boon) => boon.trim()).filter(Boolean);
    if (filled.length === 0) return;

    setBoons(normalizeBoons(filled));

    const signature = JSON.stringify({ filled, compId, align });
    if (signature !== lastAutoSignatureRef.current) {
      lastAutoSignatureRef.current = signature;
      void runAdvice(filled);
    }
  }, [align, compId, prefilledBoons, runAdvice]);

  const setBoon = (i: number, value: string) => {
    setBoons((prev) => prev.map((boon, idx) => (idx === i ? value : boon)));
  };

  const valid = boons.filter((boon) => boon.trim()).length >= 1;

  const handleSubmit = useCallback(async () => {
    await runAdvice(boons.filter((boon) => boon.trim()));
  }, [boons, runAdvice]);

  return (
    <div className="picker-card">
      <div className="picker-title">God Boon</div>
      <p className="picker-hint">Paste or auto-fill the boon text shown at 4-7.</p>

      <div className="picker-align-row">
        <label className="picker-align-label">Aligned god</label>
        <input className="picker-input" value={align} onChange={(e) => setAlign(e.target.value)} placeholder="Current god" />
      </div>

      <div className="picker-inputs">
        {boons.map((boon, i) => (
          <input
            key={i}
            className="picker-input"
            placeholder={`Boon ${i + 1}`}
            value={boon}
            onChange={(e) => setBoon(i, e.target.value)}
          />
        ))}
      </div>

      <button className="picker-btn" onClick={handleSubmit} disabled={!valid || loading}>
        {loading ? "Analyzing..." : "Recommend"}
      </button>

      {error && <p className="picker-error">{error}</p>}

      {result && (
        <div className="picker-result">
          <div className="picker-recommended">
            <span className="pick-label">Best</span>
            <span className="pick-name">{result.recommended}</span>
          </div>
          <ol className="picker-rank-list">
            {result.ranked.map((rank, i) => (
              <li key={i} className={`picker-rank-item ${i === 0 ? "rank-best" : ""}`}>
                <span className="rank-num">#{i + 1}</span>
                <span className="rank-name">{rank.name}</span>
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
