import type { AnalyzeRequest, AnalyzeResponse } from "../types";
import { DEFAULT_ANALYZE_REQUEST, normalizeAnalyzeRequest } from "./analyzeState";

export const OVERLAY_LIVE_KEY = "tft_overlay_live_snapshot";

export type OverlayLiveSnapshot = {
  updatedAt: number;
  inGame: boolean;
  state: AnalyzeRequest;
  result: AnalyzeResponse | null;
};

const EMPTY_SNAPSHOT: OverlayLiveSnapshot = {
  updatedAt: 0,
  inGame: false,
  state: DEFAULT_ANALYZE_REQUEST,
  result: null,
};

export function readOverlayLiveSnapshot(): OverlayLiveSnapshot {
  try {
    const raw = localStorage.getItem(OVERLAY_LIVE_KEY);
    if (!raw) return EMPTY_SNAPSHOT;

    const parsed = JSON.parse(raw) as Partial<OverlayLiveSnapshot> | null;
    if (!parsed || typeof parsed !== "object") return EMPTY_SNAPSHOT;

    return {
      updatedAt: typeof parsed.updatedAt === "number" ? parsed.updatedAt : 0,
      inGame: Boolean(parsed.inGame),
      state: normalizeAnalyzeRequest(parsed.state, DEFAULT_ANALYZE_REQUEST),
      result: parsed.result && typeof parsed.result === "object" ? (parsed.result as AnalyzeResponse) : null,
    };
  } catch {
    return EMPTY_SNAPSHOT;
  }
}

export function writeOverlayLiveSnapshot(snapshot: OverlayLiveSnapshot): OverlayLiveSnapshot {
  localStorage.setItem(OVERLAY_LIVE_KEY, JSON.stringify(snapshot));
  return snapshot;
}

export function clearOverlayLiveSnapshot(): void {
  localStorage.removeItem(OVERLAY_LIVE_KEY);
}
