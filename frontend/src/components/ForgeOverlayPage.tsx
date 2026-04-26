import React, { useState, useEffect } from "react";
import { ForgePicker } from "./ForgePicker";
import { readOverlayContext, readSelectionContext } from "../utils/analyzeState";

const bridge = (window as any).electronBridge as
  | { hideForge(): void } | undefined;

export function ForgeOverlayPage() {
  const [compId, setCompId] = useState("");
  const [heldItems, setHeldItems] = useState<string[]>([]);
  const [choices, setChoices] = useState<string[]>([]);

  useEffect(() => {
    const stored = readOverlayContext();
    if (stored.compId) setCompId(stored.compId);
    setHeldItems(stored.items ?? []);
    const selection = readSelectionContext();
    setChoices(selection.type === "forge" ? selection.forgeItems ?? [] : []);

    const sync = () => {
      const nextOverlay = readOverlayContext();
      const nextSelection = readSelectionContext();
      if (nextOverlay.compId) setCompId(nextOverlay.compId);
      setHeldItems(nextOverlay.items ?? []);
      setChoices(nextSelection.type === "forge" ? nextSelection.forgeItems ?? [] : []);
    };

    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);

  return (
    <div className="popup-overlay">
      <div className="popup-header">
        <span className="popup-title">フォージ素材選択</span>
        <button className="popup-close" onClick={() => bridge?.hideForge()}>✕</button>
      </div>
      <div className="popup-body">
        <ForgePicker compId={compId} heldItems={heldItems} offeredChoices={choices} />
      </div>
    </div>
  );
}
