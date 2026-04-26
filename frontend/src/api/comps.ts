import type { CompData } from "../types";
import { API_BASE } from "../config";

export async function getAllComps(): Promise<CompData[]> {
  const res = await fetch(`${API_BASE}/comps`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
