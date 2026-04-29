import type { ShopRecommendation, Unit } from "../types";

export type ShopHighlight = {
  slot: number;
  unit: Unit;
  action: ShopRecommendation["action"];
  score: number;
  reason: string;
};

const ACTION_LABELS: Record<ShopRecommendation["action"], string> = {
  buy: "買う",
  consider: "検討",
  skip: "流す",
};

export function shopActionLabel(action: ShopRecommendation["action"]): string {
  return ACTION_LABELS[action];
}

export function buildShopHighlights(
  shop: Unit[],
  recommendations: ShopRecommendation[],
): ShopHighlight[] {
  const buckets = new Map<string, ShopRecommendation[]>();

  for (const recommendation of recommendations) {
    const name = recommendation.name.trim();
    if (!name) continue;
    const bucket = buckets.get(name);
    if (bucket) {
      bucket.push(recommendation);
    } else {
      buckets.set(name, [recommendation]);
    }
  }

  return shop.map((unit, index) => {
    const bucket = buckets.get(unit.name) ?? [];
    const recommendation = bucket.shift();
    return {
      slot: index,
      unit,
      action: recommendation?.action ?? "skip",
      score: recommendation?.score ?? 0,
      reason: recommendation?.reason ?? "",
    };
  });
}
