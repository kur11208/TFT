import type { AnalyzeRequest } from "../types";
import { API_BASE } from "../config";

export interface CaptureResult {
  state: AnalyzeRequest;
  raw_ocr: Record<string, string>;
  confidence: Record<string, number>;
  preview_b64: string | null;
  timestamp: string;
}

export interface CaptureStatus {
  ocr_ready: boolean;
  message: string;
}

export async function getCaptureStatus(): Promise<CaptureStatus> {
  const res = await fetch(`${API_BASE}/capture/status`);
  return res.json();
}

export async function captureScreen(
  existingState?: AnalyzeRequest,
  includePreview = false
): Promise<CaptureResult> {
  const res = await fetch(`${API_BASE}/capture`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      include_preview: includePreview,
      existing_state: existingState ?? null,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getCapturePreview(): Promise<string> {
  const res = await fetch(`${API_BASE}/capture/preview`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.image_b64 as string;
}

export async function getRegions(): Promise<Record<string, unknown>> {
  const res = await fetch(`${API_BASE}/capture/regions`);
  return res.json();
}
