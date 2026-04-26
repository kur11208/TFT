import React, { useState, useEffect } from "react";
import { GodBoonPicker } from "./GodBoonPicker";
import { readOverlayContext, readSelectionContext } from "../utils/analyzeState";

const bridge = (window as any).electronBridge as
  | { hideGodBoon(): void } | undefined;

export function GodBoonOverlayPage() {
  const [compId, setCompId] = useState("");
  const [godAlign, setGodAlign] = useState("");
  const [boons, setBoons] = useState<string[]>([]);

  useEffect(() => {
    const stored = readOverlayContext();
    if (stored.compId) setCompId(stored.compId);
    if (stored.godAlign) setGodAlign(stored.godAlign);
    const selection = readSelectionContext();
    setBoons(selection.type === "godboon" ? selection.boons ?? [] : []);

    const sync = () => {
      const nextOverlay = readOverlayContext();
      const nextSelection = readSelectionContext();
      if (nextOverlay.compId) setCompId(nextOverlay.compId);
      if (nextOverlay.godAlign) setGodAlign(nextOverlay.godAlign);
      setBoons(nextSelection.type === "godboon" ? nextSelection.boons ?? [] : []);
    };

    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  return (
    <div className="popup-overlay">
      <div className="popup-header">
        <span className="popup-title">God Boon 選択</span>
        <span className="popup-stage">4-7</span>
        <button className="popup-close" onClick={() => bridge?.hideGodBoon()}>✕</button>
      </div>
      <div className="popup-body">
        <GodBoonPicker compId={compId} godAlign={godAlign} prefilledBoons={boons} />
      </div>
    </div>
  );
}
