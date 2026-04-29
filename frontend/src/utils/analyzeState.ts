import type { AnalyzeRequest, Unit } from "../types";

export const OVERLAY_CONTEXT_KEY = "tft_last_comp";
export const SELECTION_CONTEXT_KEY = "tft_selection_context";

export const DEFAULT_ANALYZE_REQUEST: AnalyzeRequest = {
  patch: "current",
  stage: "1-1",
  level: 1,
  hp: 100,
  gold: 0,
  streak: 0,
  board: [],
  bench: [],
  shop: [],
  items: [],
  augments: [],
  notes: "",
};

export interface OverlayContext {
  compId?: string;
  hp?: number;
  stage?: string;
  items?: string[];
  godAlign?: string;
}

export type SelectionKind = "augment" | "god" | "forge" | "godboon";

export interface SelectionContext {
  type?: SelectionKind;
  stage?: string;
  augments?: string[];
  gods?: string[];
  forgeItems?: string[];
  boons?: string[];
  updatedAt?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asInt(value: unknown, fallback: number, minimum?: number, maximum?: number): number {
  const parsed = typeof value === "number" ? Math.trunc(value) : Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(parsed)) return fallback;
  if (minimum !== undefined && parsed < minimum) return fallback;
  if (maximum !== undefined && parsed > maximum) return fallback;
  return parsed;
}

export function normalizeStage(value: unknown, fallback = DEFAULT_ANALYZE_REQUEST.stage): string {
  if (typeof value !== "string") return fallback;
  const match = value.trim().match(/^(\d+)-(\d+)$/);
  if (!match) return fallback;

  const stage = Number.parseInt(match[1], 10);
  const round = Number.parseInt(match[2], 10);
  if (!Number.isFinite(stage) || !Number.isFinite(round)) return fallback;
  if (stage < 1 || stage > 9 || round < 1 || round > 7) return fallback;

  return `${stage}-${round}`;
}

function normalizeStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];

  const items = value
    .map((entry) => (typeof entry === "string" ? entry.trim() : ""))
    .filter(Boolean);

  return [...new Set(items)];
}

function normalizeUnit(value: unknown): Unit | null {
  if (!isRecord(value) || typeof value.name !== "string" || !value.name.trim()) {
    return null;
  }

  const tags = Array.isArray(value.tags)
    ? value.tags.filter((tag): tag is string => typeof tag === "string" && tag.trim().length > 0)
    : [];
  const items = normalizeStringList(value.items);

  return {
    name: value.name.trim(),
    stars: asInt(value.stars, 1, 1, 3),
    tags,
    items,
  };
}

function normalizeUnits(value: unknown): Unit[] {
  if (!Array.isArray(value)) return [];

  const units = value
    .map(normalizeUnit)
    .filter((unit): unit is Unit => unit !== null);

  const deduped: Unit[] = [];
  const seen = new Set<string>();
  for (const unit of units) {
    const key = `${unit.name}:${unit.stars}:${(unit.items ?? []).join("|")}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(unit);
  }
  return deduped;
}

export function normalizeAnalyzeRequest(
  value: unknown,
  fallback: AnalyzeRequest = DEFAULT_ANALYZE_REQUEST,
): AnalyzeRequest {
  const source = isRecord(value) ? value : {};

  return {
    patch: typeof source.patch === "string" && source.patch.trim() ? source.patch.trim() : fallback.patch,
    stage: normalizeStage(source.stage, fallback.stage),
    level: asInt(source.level, fallback.level, 1, 10),
    hp: asInt(source.hp, fallback.hp, 0, 100),
    gold: asInt(source.gold, fallback.gold, 0, 999),
    streak: asInt(source.streak, fallback.streak, -99, 99),
    board: normalizeUnits(source.board),
    bench: normalizeUnits(source.bench),
    shop: normalizeUnits(source.shop),
    items: normalizeStringList(source.items),
    augments: normalizeStringList(source.augments),
    notes: typeof source.notes === "string" ? source.notes : fallback.notes,
    preferred_comp_id:
      typeof source.preferred_comp_id === "string" && source.preferred_comp_id.trim()
        ? source.preferred_comp_id.trim()
        : fallback.preferred_comp_id ?? null,
  };
}

export function readOverlayContext(): OverlayContext {
  try {
    const raw = localStorage.getItem(OVERLAY_CONTEXT_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as OverlayContext;
    if (!isRecord(parsed)) return {};
    return {
      compId: typeof parsed.compId === "string" ? parsed.compId : undefined,
      hp: typeof parsed.hp === "number" ? parsed.hp : undefined,
      stage: typeof parsed.stage === "string" ? parsed.stage : undefined,
      items: normalizeStringList(parsed.items),
      godAlign: typeof parsed.godAlign === "string" ? parsed.godAlign : undefined,
    };
  } catch {
    return {};
  }
}

export function writeOverlayContext(patch: OverlayContext): OverlayContext {
  const current = readOverlayContext();
  const next = { ...current, ...patch };
  localStorage.setItem(OVERLAY_CONTEXT_KEY, JSON.stringify(next));
  return next;
}

export function readSelectionContext(): SelectionContext {
  try {
    const raw = localStorage.getItem(SELECTION_CONTEXT_KEY);
    if (!raw) return {};

    const parsed = JSON.parse(raw) as SelectionContext;
    if (!isRecord(parsed)) return {};

    const type = typeof parsed.type === "string" ? parsed.type : undefined;
    return {
      type: type === "augment" || type === "god" || type === "forge" || type === "godboon" ? type : undefined,
      stage: typeof parsed.stage === "string" ? parsed.stage : undefined,
      augments: normalizeStringList(parsed.augments),
      gods: normalizeStringList(parsed.gods),
      forgeItems: normalizeStringList(parsed.forgeItems),
      boons: normalizeStringList(parsed.boons),
      updatedAt: typeof parsed.updatedAt === "number" ? parsed.updatedAt : undefined,
    };
  } catch {
    return {};
  }
}

export function writeSelectionContext(patch: SelectionContext): SelectionContext {
  const next: SelectionContext = {
    type: patch.type,
    stage: patch.stage,
    augments: normalizeStringList(patch.augments),
    gods: normalizeStringList(patch.gods),
    forgeItems: normalizeStringList(patch.forgeItems),
    boons: normalizeStringList(patch.boons),
    updatedAt: patch.updatedAt ?? Date.now(),
  };
  localStorage.setItem(SELECTION_CONTEXT_KEY, JSON.stringify(next));
  return next;
}

export function clearSelectionContext(): void {
  localStorage.removeItem(SELECTION_CONTEXT_KEY);
}
