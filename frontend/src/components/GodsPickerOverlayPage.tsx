import React, { useState, useEffect } from "react";
import { GodsPicker } from "./GodsPicker";
import { readOverlayContext, readSelectionContext } from "../utils/analyzeState";

const bridge = (window as any).electronBridge as
  | { hideGods(): void } | undefined;

export function GodsPickerOverlayPage() {
  const params  = new URLSearchParams(window.location.search);
  const [stage, setStage] = useState(params.get("stage") || "");
  const [compId, setCompId] = useState("");
  const [hp, setHp]         = useState(100);
  const [offeredGods, setOfferedGods] = useState<string[]>([]);

  useEffect(() => {
    const stored = readOverlayContext();
    if (stored.compId) setCompId(stored.compId);
    if (typeof stored.hp === "number") setHp(stored.hp);
    const selection = readSelectionContext();
    if (selection.stage) setStage(selection.stage);
    setOfferedGods(selection.type === "god" ? selection.gods ?? [] : []);

    const sync = () => {
      const nextOverlay = readOverlayContext();
      const nextSelection = readSelectionContext();
      if (nextOverlay.compId) setCompId(nextOverlay.compId);
      if (typeof nextOverlay.hp === "number") setHp(nextOverlay.hp);
      if (nextSelection.stage) setStage(nextSelection.stage);
      setOfferedGods(nextSelection.type === "god" ? nextSelection.gods ?? [] : []);
    };

    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  return (
    <div className="popup-overlay">
      <div className="popup-header">
        <span className="popup-title">神のオファリング</span>
        {stage && <span className="popup-stage">{stage}</span>}
        <button className="popup-close" onClick={() => bridge?.hideGods()}>✕</button>
      </div>
      <div className="popup-body">
        <GodsPicker compId={compId} hp={hp} offeredGods={offeredGods} />
      </div>
    </div>
  );
}
