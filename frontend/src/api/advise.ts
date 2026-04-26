import type { AugmentChoiceResponse, ForgeAdviceResponse, GodsChoiceResponse, GodBoonResponse } from "../types";
import { API_BASE } from "../config";

export async function adviseAugment(
  choices: string[],
  compId: string,
  stage: string,
): Promise<AugmentChoiceResponse> {
  const res = await fetch(`${API_BASE}/advise/augment`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choices, comp_id: compId, stage }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function adviseForge(
  choices: string[],
  heldItems: string[],
  compId: string,
): Promise<ForgeAdviceResponse> {
  const res = await fetch(`${API_BASE}/advise/forge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choices, held_items: heldItems, comp_id: compId }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function adviseGods(
  godsOffered: string[],
  compId: string,
  godAlign: string,
  hp: number,
): Promise<GodsChoiceResponse> {
  const res = await fetch(`${API_BASE}/advise/gods`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gods_offered: godsOffered, comp_id: compId, god_align: godAlign, hp }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function adviseGodBoon(
  boomsOffered: string[],
  compId: string,
  godAlign: string,
): Promise<GodBoonResponse> {
  const res = await fetch(`${API_BASE}/advise/god-boon`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ boons_offered: boomsOffered, comp_id: compId, god_align: godAlign }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
