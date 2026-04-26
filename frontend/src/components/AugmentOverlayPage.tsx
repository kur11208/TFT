import React, { useState, useEffect } from "react";
import { AugmentPicker } from "./AugmentPicker";
import { readOverlayContext, readSelectionContext } from "../utils/analyzeState";

const bridge = (window as any).electronBridge as
  | { hideAugment(): void } | undefined;

export function AugmentOverlayPage() {
  const params  = new URLSearchParams(window.location.search);
  const [stage, setStage] = useState(params.get("stage") || "2-1");
  const [compId, setCompId] = useState("");
  const [choices, setChoices] = useState<string[]>([]);

  useEffect(() => {
    const stored = readOverlayContext();
    if (stored.compId) setCompId(stored.compId);
    const selection = readSelectionContext();
    if (selection.stage) setStage(selection.stage);
    setChoices(selection.type === "augment" ? selection.augments ?? [] : []);

    const sync = () => {
      const nextOverlay = readOverlayContext();
      const next = readSelectionContext();
      if (nextOverlay.compId) setCompId(nextOverlay.compId);
      if (next.stage) setStage(next.stage);
      setChoices(next.type === "augment" ? next.augments ?? [] : []);
    };

    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  return (
    <div className="popup-overlay">
      <div className="popup-header">
        <span className="popup-title">オーグメント選択</span>
        <span className="popup-stage">{stage}</span>
        <button className="popup-close" onClick={() => bridge?.hideAugment()}>✕</button>
      </div>
      <div className="popup-body">
        <AugmentPicker compId={compId} stage={stage} prefilledChoices={choices} />
      </div>
    </div>
  );
}
