export interface Unit {
  name: string;
  stars: number;
  tags: string[];
}

export interface AnalyzeRequest {
  patch: string;
  stage: string;
  level: number;
  hp: number;
  gold: number;
  streak: number;
  board: Unit[];
  bench: Unit[];
  shop: Unit[];
  items: string[];
  augments: string[];
  notes: string;
  preferred_comp_id?: string | null;
}

export interface CompUnit {
  name: string;
  stars: number;
  items: string[];
  position: string;
}

export interface CompResult {
  id: string;
  name: string;
  score: number;
  reason: string;
  tier: string;
  win_rate: number;
  top4_rate: number;
  avg_placement: number;
  difficulty: string;
  play_style: string;
  when_to_play: string;
  carry: string;
  units: CompUnit[];
  early_board: string[];
}

export interface EconomyPlan {
  action: string;
  reason: string;
}

export interface ShopRecommendation {
  name: string;
  score: number;
  reason: string;
  action: "buy" | "consider" | "skip";
}

export interface CutCandidate {
  name: string;
  reason: string;
}

export interface AugmentRecommendation {
  name: string;
  tier: string;
  reason: string;
}

export interface BoardAdviceItem {
  label: string;
  kind: "unit" | "trait";
  priority: "high" | "medium";
  reason: string;
}

export interface SituationAction {
  priority: "urgent" | "high" | "medium";
  action: string;
  detail: string;
}

export interface AnalyzeResponse {
  boardStrength: number;
  topComp: CompResult;
  economyPlan: EconomyPlan;
  shopRecommendations: ShopRecommendation[];
  cutCandidates: CutCandidate[];
  itemPlan: string;
  nextImprovements: string[];
  augmentRecommendations: AugmentRecommendation[];
  boardAdvice: BoardAdviceItem[];
  situationActions: SituationAction[];
}

export interface CompData extends CompResult {
  description: string;
  key_tags: string[];
  frontline_tags: string[];
  item_keywords: string[];
  augment_keywords: string[];
  min_level: number;
}

export interface AugmentChoiceItem {
  name: string;
  score: number;
  reason: string;
}

export interface AugmentChoiceResponse {
  recommended: string;
  ranked: AugmentChoiceItem[];
}

export interface ForgeChoiceItem {
  name: string;
  score: number;
  reason: string;
  builds: string[];
}

export interface ForgeAdviceResponse {
  recommended: string;
  ranked: ForgeChoiceItem[];
}

export interface GodsChoiceItem {
  name: string;
  score: number;
  reason: string;
}

export interface GodsChoiceResponse {
  recommended: string;
  ranked: GodsChoiceItem[];
}

export interface GodBoonItem {
  name: string;
  score: number;
  reason: string;
}

export interface GodBoonResponse {
  recommended: string;
  ranked: GodBoonItem[];
}
