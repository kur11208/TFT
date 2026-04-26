import React, { useCallback, useEffect, useRef, useState } from "react";

import type { AugmentChoiceResponse } from "../types";
import { adviseAugment } from "../api/advise";
import { API_BASE } from "../config";

interface Props {
  compId?: string;
  stage?: string;
  prefilledChoices?: string[];
}

const TIER_CLS: Record<string, string> = {
  Silver: "aug-silver",
  Gold: "aug-gold",
  Prismatic: "aug-prismatic",
};

const TIER_LABEL: Record<string, string> = {
  Silver: "Silver",
  Gold: "Gold",
  Prismatic: "Prismatic",
};

function normalizeChoiceList(values: string[], length = 3): string[] {
  const next = values.map((value) => value.trim()).filter(Boolean).slice(0, length);
  while (next.length < length) next.push("");
  return next;
}

export function AugmentPicker({ compId = "", stage = "2-1", prefilledChoices = [] }: Props) {
  const [choices, setChoices] = useState(["", "", ""]);
  const [result, setResult] = useState<AugmentChoiceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastAutoSignatureRef = useRef("");

  const setChoice = (i: number, value: string) => {
    setChoices((prev) => prev.map((choice, idx) => (idx === i ? value : choice)));
  };

  const runAdvice = useCallback(async (nextChoices: string[]) => {
    if (nextChoices.length < 2) return;

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await adviseAugment(nextChoices, compId, stage);
      setResult(response);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to analyze augments");
    } finally {
      setLoading(false);
    }
  }, [compId, stage]);

  useEffect(() => {
    if (prefilledChoices.some((name) => name.trim())) return;

    let cancelled = false;
    setScanning(true);

    fetch(`${API_BASE}/capture/augments`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        const names: string[] = data.augments ?? [];
        if (names.some((name) => name.trim())) {
          setChoices(normalizeChoiceList(names));
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setScanning(false);
      });

    return () => {
      cancelled = true;
    };
  }, [prefilledChoices]);

  useEffect(() => {
    const filled = prefilledChoices.map((choice) => choice.trim()).filter(Boolean);
    if (filled.length === 0) return;

    setChoices(normalizeChoiceList(filled));

    const signature = JSON.stringify({ filled, compId, stage });
    if (filled.length >= 2 && signature !== lastAutoSignatureRef.current) {
      lastAutoSignatureRef.current = signature;
      void runAdvice(filled);
    }
  }, [compId, prefilledChoices, runAdvice, stage]);

  const handleRescan = useCallback(async () => {
    setScanning(true);
    try {
      const response = await fetch(`${API_BASE}/capture/augments`);
      if (!response.ok) return;

      const data = await response.json();
      const filled = (data.augments ?? []).map((name: string) => name.trim()).filter(Boolean);
      if (filled.length > 0) {
        setChoices(normalizeChoiceList(filled));
        if (filled.length >= 2) {
          void runAdvice(filled);
        } else {
          setResult(null);
        }
      }
    } catch {}
    setScanning(false);
  }, [runAdvice]);

  const valid = choices.filter((choice) => choice.trim()).length >= 2;

  const handleSubmit = useCallback(async () => {
    await runAdvice(choices.filter((choice) => choice.trim()));
  }, [choices, runAdvice]);

  return (
    <div className="picker-card">
      <div className="picker-title-row">
        <span className="picker-title">Augment Advisor</span>
        <button className="picker-scan-btn" onClick={handleRescan} disabled={scanning} title="Scan augment cards">
          {scanning ? "Scanning..." : "Rescan"}
        </button>
      </div>

      <div className="picker-inputs">
        {choices.map((choice, i) => (
          <input
            key={i}
            className="picker-input"
            placeholder={scanning ? "Scanning..." : `Choice ${i + 1}`}
            value={choice}
            onChange={(e) => setChoice(i, e.target.value)}
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
            {result.ranked.map((rank, i) => {
              const tier = rank.reason.match(/Silver|Gold|Prismatic/)?.[0] ?? "";
              return (
                <li key={i} className={`picker-rank-item ${i === 0 ? "rank-best" : ""}`}>
                  <span className="rank-num">#{i + 1}</span>
                  {tier && (
                    <span className={`aug-tier-badge ${TIER_CLS[tier] ?? "aug-silver"}`}>
                      {TIER_LABEL[tier] ?? tier}
                    </span>
                  )}
                  <span className="rank-name">{rank.name}</span>
                  <span className="rank-score">{rank.score}pt</span>
                  <span className="rank-reason">{rank.reason}</span>
                </li>
              );
            })}
          </ol>
        </div>
      )}
    </div>
  );
}
