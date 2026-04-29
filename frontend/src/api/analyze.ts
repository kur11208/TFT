import type { AnalyzeRequest, AnalyzeResponse } from "../types";
import { API_BASE } from "../config";

const ANALYZE_TIMEOUT_MS = 8000;

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("analyze timeout");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function analyzeBoard(req: AnalyzeRequest): Promise<AnalyzeResponse> {
  const res = await fetchWithTimeout(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<AnalyzeResponse>;
}
