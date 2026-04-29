import React from "react";

import type {
  AnalyzeRequest,
  AnalyzeResponse,
  AugmentRecommendation,
  BoardAdviceItem,
  CompUnit,
  ShopRecommendation,
  SituationAction,
} from "../types";
import { buildShopHighlights, shopActionLabel } from "../utils/shopHighlights";
import { AugmentPicker } from "./AugmentPicker";
import { ForgePicker } from "./ForgePicker";

interface Props {
  result: AnalyzeResponse | null;
  request: AnalyzeRequest;
  error: string | null;
  loading: boolean;
}

function ScoreBar({ value }: { value: number }) {
  const color = value >= 70 ? "#4ade80" : value >= 45 ? "#facc15" : "#f87171";
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-bg">
        <div className="score-bar-fill" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="score-label">{value}</span>
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  return <span className={`tier-badge tier-${tier}`}>{tier}</span>;
}

function Stars({ count }: { count: number }) {
  return <span className={`stars ${count >= 3 ? "three-star" : count === 2 ? "two-star" : "one-star"}`}>{"★".repeat(count)}</span>;
}

function UnitCell({ unit }: { unit: CompUnit }) {
  const positionClass =
    unit.position === "frontline" ? "unit-frontline" : unit.position === "backline" ? "unit-backline" : "";

  return (
    <div className={`unit-cell ${positionClass}`}>
      <div className="unit-name-row">
        <Stars count={unit.stars} />
        <span className="unit-name">{unit.name}</span>
      </div>
      {unit.items.length > 0 && (
        <div className="unit-items">
          {unit.items.map((item, i) => (
            <span key={i} className="item-tag">{item}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function AugTierBadge({ tier }: { tier: string }) {
  const labels: Record<string, string> = {
    Silver: "シルバー",
    Gold: "ゴールド",
    Prismatic: "プリズム",
  };
  const className =
    tier === "Prismatic" ? "aug-prismatic" : tier === "Gold" ? "aug-gold" : "aug-silver";
  return <span className={`aug-tier-badge ${className}`}>{labels[tier] ?? tier}</span>;
}

function BoardAdviceRow({ item }: { item: BoardAdviceItem }) {
  const label = item.priority === "high" ? "高" : "中";
  return (
    <li className={`board-advice-item ${item.priority === "high" ? "high" : "mid"}`}>
      <span className={`advice-priority ${item.priority === "high" ? "high" : "mid"}`}>{label}</span>
      <span className="advice-label">{item.label}</span>
      <span className="advice-reason">{item.reason}</span>
    </li>
  );
}

function AugRow({ aug }: { aug: AugmentRecommendation }) {
  return (
    <li className="aug-row">
      <AugTierBadge tier={aug.tier} />
      <div className="aug-info">
        <span className="aug-name">{aug.name}</span>
        <span className="aug-reason">{aug.reason}</span>
      </div>
    </li>
  );
}

function ShopActionBadge({ action }: { action: ShopRecommendation["action"] }) {
  const labels: Record<ShopRecommendation["action"], string> = {
    buy: "買う",
    consider: "検討",
    skip: "スキップ",
  };
  const className =
    action === "buy" ? "shop-buy" : action === "consider" ? "shop-maybe" : "shop-skip";
  return <span className={`shop-action-badge ${className}`}>{labels[action]}</span>;
}

function SituationCard({ item }: { item: SituationAction }) {
  const className =
    item.priority === "urgent" ? "sit-urgent" : item.priority === "high" ? "sit-high" : "sit-medium";
  return (
    <div className={`situation-card ${className}`}>
      <div className="sit-action">{item.action}</div>
      <div className="sit-detail">{item.detail}</div>
    </div>
  );
}

export function ResultPanel({ result, request, error, loading }: Props) {
  if (loading) {
    return <div className="result-panel result-placeholder"><p>分析中...</p></div>;
  }

  if (error) {
    return <div className="result-panel result-placeholder"><p className="error-text">エラー: {error}</p></div>;
  }

  if (!result) {
    return (
      <div className="result-panel result-placeholder">
        <p>盤面を入力して Analyze を押すと、ここに結果が表示されます。</p>
        <p className="hint">サンプル入力か自動キャプチャから始めるのが最短です。</p>
      </div>
    );
  }

  const {
    boardStrength,
    topComp,
    economyPlan,
    shopRecommendations,
    cutCandidates,
    itemPlan,
    nextImprovements,
    augmentRecommendations,
    boardAdvice,
    situationActions,
  } = result;
  const shopHighlights = buildShopHighlights(request.shop, shopRecommendations);

  const frontline = topComp.units.filter((unit) => unit.position === "frontline");
  const backline = topComp.units.filter((unit) => unit.position !== "frontline");

  return (
    <div className="result-panel">
      {situationActions.length > 0 && (
        <section className="result-section situation-section">
          <h3>今やること</h3>
          <div className="situation-list">
            {situationActions.map((item, i) => <SituationCard key={i} item={item} />)}
          </div>
        </section>
      )}

      <section className="result-section">
        <h3>盤面強度</h3>
        <ScoreBar value={boardStrength} />
      </section>

      <section className="result-section">
        <h3>推奨構成</h3>
        <div className="comp-card-metatft">
          <div className="comp-card-header">
            <TierBadge tier={topComp.tier} />
            <div className="comp-card-name-block">
              <span className="comp-name">{topComp.name}</span>
              {topComp.play_style && <span className="playstyle-tag">{topComp.play_style}</span>}
            </div>
            <div className="comp-card-stats">
              <div className="stat-pill">
                <span className="stat-label">勝率</span>
                <span className="stat-value">{(topComp.win_rate * 100).toFixed(1)}%</span>
              </div>
              <div className="stat-pill">
                <span className="stat-label">TOP4率</span>
                <span className="stat-value">{(topComp.top4_rate * 100).toFixed(1)}%</span>
              </div>
              <div className="stat-pill">
                <span className="stat-label">平均順位</span>
                <span className="stat-value">{topComp.avg_placement.toFixed(2)}</span>
              </div>
            </div>
          </div>

          <p className="comp-reason">マッチ度 {topComp.score}pt / {topComp.reason}</p>

          {topComp.when_to_play && (
            <p className="comp-when-to-play">
              <span className="when-label">使いどころ:</span> {topComp.when_to_play}
            </p>
          )}

          {topComp.units.length > 0 && (
            <div className="comp-unit-section">
              {frontline.length > 0 && (
                <div className="lineup-group">
                  <p className="lineup-label">前衛</p>
                  <div className="unit-lineup">
                    {frontline.map((unit, i) => <UnitCell key={i} unit={unit} />)}
                  </div>
                </div>
              )}

              {backline.length > 0 && (
                <div className="lineup-group">
                  <p className="lineup-label">後衛 / キャリー</p>
                  <div className="unit-lineup">
                    {backline.map((unit, i) => <UnitCell key={i} unit={unit} />)}
                  </div>
                </div>
              )}

              {topComp.early_board.length > 0 && (
                <div className="early-board-row">
                  <p className="lineup-label">序盤の形</p>
                  <div className="early-board">
                    {topComp.early_board.map((name, i) => (
                      <span key={i} className="early-unit">{name}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {boardAdvice.length > 0 && (
        <section className="result-section">
          <h3>配置・盤面アドバイス</h3>
          <ul className="board-advice-list">
            {boardAdvice.map((item, i) => <BoardAdviceRow key={i} item={item} />)}
          </ul>
        </section>
      )}

      {augmentRecommendations.length > 0 && (
        <section className="result-section">
          <h3>次に強いオーグメント傾向</h3>
          <ul className="aug-list">
            {augmentRecommendations.map((aug, i) => <AugRow key={i} aug={aug} />)}
          </ul>
        </section>
      )}

      <section className="result-section">
        <h3>経済プラン</h3>
        <div className="economy-card">
          <span className="economy-action">{economyPlan.action}</span>
          <p className="economy-reason">{economyPlan.reason}</p>
        </div>
      </section>

      <section className="result-section">
        <h3>ショップ優先度</h3>
        {shopHighlights.length > 0 && (
          <div className="shop-slot-grid">
            {shopHighlights.map((item) => (
              <div
                key={`${item.unit.name}-${item.slot}`}
                className={`shop-slot-card ${
                  item.action === "buy"
                    ? "shop-slot-card-buy"
                    : item.action === "skip"
                      ? "shop-slot-card-skip"
                      : "shop-slot-card-maybe"
                }`}
              >
                <div className="shop-slot-head">
                  <span className="shop-slot-index">{item.slot + 1}</span>
                  <span className="shop-slot-badge">{shopActionLabel(item.action)}</span>
                </div>
                <div className="shop-slot-name">{item.unit.name}</div>
                <div className="shop-slot-meta">
                  <span className="shop-slot-stars">{"★".repeat(item.unit.stars)}</span>
                  {item.score > 0 && <span className="shop-slot-score">{item.score}</span>}
                </div>
              </div>
            ))}
          </div>
        )}
        {shopRecommendations.length === 0 ? (
          <p className="empty-hint">ショップ情報がまだありません。</p>
        ) : (
          <ul className="shop-list">
            {shopRecommendations.map((recommendation, i) => (
              <li
                key={i}
                className={`shop-item ${
                  recommendation.action === "buy"
                    ? "shop-item-buy"
                    : recommendation.action === "skip"
                      ? "shop-item-skip"
                      : ""
                }`}
              >
                <ShopActionBadge action={recommendation.action} />
                <span className="shop-name">{recommendation.name}</span>
                <span className="shop-reason">{recommendation.reason}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {cutCandidates.length > 0 && (
        <section className="result-section">
          <h3>外し候補</h3>
          <ul className="cut-list">
            {cutCandidates.map((candidate, i) => (
              <li key={i} className="cut-item">
                <span className="cut-name">{candidate.name}</span>
                <span className="cut-reason">{candidate.reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="result-section">
        <h3>アイテム方針</h3>
        <p className="item-plan-text">{itemPlan}</p>
      </section>

      <section className="result-section">
        <ForgePicker compId={topComp.id} heldItems={request.items} />
      </section>

      <section className="result-section">
        <AugmentPicker compId={topComp.id} stage={request.stage} />
      </section>

      {nextImprovements.length > 0 && (
        <section className="result-section">
          <h3>次の改善点</h3>
          <ol className="improvement-list">
            {nextImprovements.map((tip, i) => <li key={i}>{tip}</li>)}
          </ol>
        </section>
      )}
    </div>
  );
}
