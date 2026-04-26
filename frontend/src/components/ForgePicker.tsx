import React, { useCallback, useEffect, useRef, useState } from "react";

import type { ForgeAdviceResponse } from "../types";
import { adviseForge } from "../api/advise";

const COMPONENTS = [
  "B.F. Sword",
  "Recurve Bow",
  "Needlessly Large Rod",
  "Tear of the Goddess",
  "Sparring Gloves",
  "Chain Vest",
  "Giant's Belt",
  "Negatron Cloak",
  "Spatula",
];

const SHORT: Record<string, string> = {
  "B.F. Sword": "Sword",
  "Recurve Bow": "Bow",
  "Needlessly Large Rod": "Rod",
  "Tear of the Goddess": "Tear",
  "Sparring Gloves": "Glove",
  "Chain Vest": "Vest",
  "Giant's Belt": "Belt",
  "Negatron Cloak": "Cloak",
  Spatula: "Spat",
};

interface Props {
  compId?: string;
  heldItems?: string[];
  offeredChoices?: string[];
}

export function ForgePicker({ compId = "", heldItems = [], offeredChoices = [] }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<ForgeAdviceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastAutoSignatureRef = useRef("");

  const availableChoices = Array.from(new Set([...offeredChoices.map((name) => name.trim()).filter(Boolean), ...COMPONENTS]));

  const runAdvice = useCallback(async (choices: string[]) => {
    if (choices.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await adviseForge(choices, heldItems, compId);
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to analyze forge choices");
    } finally {
      setLoading(false);
    }
  }, [compId, heldItems]);

  useEffect(() => {
    const normalized = offeredChoices.map((name) => name.trim()).filter(Boolean);
    if (normalized.length === 0) return;

    setSelected(new Set(normalized));

    const signature = JSON.stringify({ normalized, heldItems, compId });
    if (signature !== lastAutoSignatureRef.current) {
      lastAutoSignatureRef.current = signature;
      void runAdvice(normalized);
    }
  }, [compId, heldItems, offeredChoices, runAdvice]);

  const toggle = (name: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const handleSubmit = useCallback(async () => {
    await runAdvice([...selected]);
  }, [runAdvice, selected]);

  return (
    <div className="picker-card">
      <div className="picker-title">Forge Advisor</div>
      <p className="picker-hint">Pick the offered items/components or let the popup auto-fill them.</p>
      {heldItems.length > 0 && <p className="picker-hint">Held items: {heldItems.join(", ")}</p>}

      <div className="forge-grid">
        {availableChoices.map((choice) => (
          <button
            key={choice}
            className={`forge-chip ${selected.has(choice) ? "selected" : ""}`}
            onClick={() => toggle(choice)}
            title={choice}
          >
            {SHORT[choice] ?? choice}
          </button>
        ))}
      </div>

      <button className="picker-btn" onClick={handleSubmit} disabled={selected.size === 0 || loading}>
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
                <div className="rank-detail">
                  <span className="rank-reason">{rank.reason}</span>
                  {rank.builds.length > 0 && <span className="rank-builds">Builds: {rank.builds.join(" / ")}</span>}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
