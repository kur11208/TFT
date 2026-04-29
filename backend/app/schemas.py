from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Unit(BaseModel):
    name: str
    stars: int = 1
    tags: List[str] = Field(default_factory=list)
    items: List[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    patch: str = "current"
    stage: str = "1-1"
    level: int = 1
    hp: int = 100
    gold: int = 0
    streak: int = 0
    board: List[Unit] = Field(default_factory=list)
    bench: List[Unit] = Field(default_factory=list)
    shop: List[Unit] = Field(default_factory=list)
    items: List[str] = Field(default_factory=list)
    augments: List[str] = Field(default_factory=list)
    notes: str = ""
    preferred_comp_id: Optional[str] = None


class CompUnit(BaseModel):
    name: str
    stars: int = 1
    items: List[str] = Field(default_factory=list)
    position: str = "flex"


class CompResult(BaseModel):
    id: str
    name: str
    score: int
    reason: str
    tier: str = "B"
    win_rate: float = 0.0
    top4_rate: float = 0.0
    avg_placement: float = 4.5
    difficulty: str = "Medium"
    play_style: str = ""
    when_to_play: str = ""
    carry: str = ""
    units: List[CompUnit] = Field(default_factory=list)
    early_board: List[str] = Field(default_factory=list)


class AugmentRecommendation(BaseModel):
    name: str
    tier: str
    reason: str


class BoardAdviceItem(BaseModel):
    label: str
    kind: Literal["unit", "trait"]
    priority: Literal["high", "medium"]
    reason: str


class SituationAction(BaseModel):
    priority: Literal["urgent", "high", "medium"]
    action: str
    detail: str


class EconomyPlan(BaseModel):
    action: str
    reason: str


class ShopRecommendation(BaseModel):
    name: str
    score: int
    reason: str
    action: Literal["buy", "consider", "skip"] = "skip"


class CutCandidate(BaseModel):
    name: str
    reason: str


class AnalyzeResponse(BaseModel):
    boardStrength: int
    topComp: CompResult
    economyPlan: EconomyPlan
    shopRecommendations: List[ShopRecommendation]
    cutCandidates: List[CutCandidate]
    itemPlan: str
    nextImprovements: List[str]
    augmentRecommendations: List[AugmentRecommendation] = Field(default_factory=list)
    boardAdvice: List[BoardAdviceItem] = Field(default_factory=list)
    situationActions: List[SituationAction] = Field(default_factory=list)


class AugmentChoiceItem(BaseModel):
    name: str
    score: int
    reason: str


class AugmentChoiceRequest(BaseModel):
    choices: List[str]
    comp_id: str = ""
    stage: str = "2-1"


class AugmentChoiceResponse(BaseModel):
    recommended: str
    ranked: List[AugmentChoiceItem]


class ForgeChoiceItem(BaseModel):
    name: str
    score: int
    reason: str
    builds: List[str] = Field(default_factory=list)


class ForgeAdviceRequest(BaseModel):
    choices: List[str]
    held_items: List[str] = Field(default_factory=list)
    comp_id: str = ""


class ForgeAdviceResponse(BaseModel):
    recommended: str
    ranked: List[ForgeChoiceItem]


class GodsChoiceItem(BaseModel):
    name: str
    score: int
    reason: str


class GodsChoiceRequest(BaseModel):
    gods_offered: List[str]
    comp_id: str = ""
    god_align: str = ""
    hp: int = 100


class GodsChoiceResponse(BaseModel):
    recommended: str
    ranked: List[GodsChoiceItem]


class GodBoonItem(BaseModel):
    name: str
    score: int
    reason: str


class GodBoonRequest(BaseModel):
    boons_offered: List[str]
    comp_id: str = ""
    god_align: str = ""


class GodBoonResponse(BaseModel):
    recommended: str
    ranked: List[GodBoonItem]
