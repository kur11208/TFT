import React, { useEffect, useState } from "react";
import type { CompData, CompUnit } from "../types";
import { getAllComps } from "../api/comps";

function TierBadge({ tier }: { tier: string }) {
  return <span className={`tier-badge tier-${tier}`}>{tier}</span>;
}

function Stars({ count }: { count: number }) {
  if (count === 3) return <span className="stars three-star">★★★</span>;
  if (count === 2) return <span className="stars two-star">★★</span>;
  return <span className="stars one-star">★</span>;
}

function UnitCell({ unit }: { unit: CompUnit }) {
  const posClass = unit.position === "frontline" ? "unit-frontline" : unit.position === "backline" ? "unit-backline" : "";
  return (
    <div className={`unit-cell ${posClass}`}>
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

function CompDetail({ comp }: { comp: CompData }) {
  const frontline = comp.units.filter((u) => u.position === "frontline");
  const backline = comp.units.filter((u) => u.position !== "frontline");

  return (
    <div className="comp-detail">
      <div className="comp-detail-grid">
        <div className="comp-detail-col">
          <p className="comp-detail-label">いつ使う？</p>
          <p className="comp-detail-value">{comp.when_to_play}</p>
        </div>
        <div className="comp-detail-col">
          <p className="comp-detail-label">序盤ボード</p>
          <div className="early-board">
            {comp.early_board.map((name, i) => (
              <span key={i} className="early-unit">{name}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="unit-lineup-section">
        <div className="lineup-group">
          <p className="lineup-label">前衛</p>
          <div className="unit-lineup">
            {frontline.map((u, i) => <UnitCell key={i} unit={u} />)}
          </div>
        </div>
        <div className="lineup-group">
          <p className="lineup-label">後衛 / キャリー</p>
          <div className="unit-lineup">
            {backline.map((u, i) => <UnitCell key={i} unit={u} />)}
          </div>
        </div>
      </div>
    </div>
  );
}

function CompRow({ comp }: { comp: CompData }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`comp-row ${expanded ? "expanded" : ""}`}>
      <div className="comp-row-header" onClick={() => setExpanded((v) => !v)}>
        <TierBadge tier={comp.tier} />

        <div className="comp-row-name">
          <span className="comp-row-title">{comp.name}</span>
          <span className="comp-row-carry">メイン: {comp.carry}</span>
        </div>

        <div className="comp-row-tags">
          <span className="playstyle-tag">{comp.play_style}</span>
          <span className={`diff-tag diff-${comp.difficulty}`}>
            {{ Easy: "簡単", Medium: "普通", Hard: "難しい" }[comp.difficulty] ?? comp.difficulty}
          </span>
        </div>

        <div className="comp-row-stats">
          <div className="stat-pill">
            <span className="stat-label">勝率</span>
            <span className="stat-value">{(comp.win_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="stat-pill">
            <span className="stat-label">TOP4</span>
            <span className="stat-value">{(comp.top4_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="stat-pill">
            <span className="stat-label">平均順位</span>
            <span className="stat-value">{comp.avg_placement.toFixed(2)}</span>
          </div>
        </div>

        <span className="expand-icon">{expanded ? "▲" : "▼"}</span>
      </div>

      {expanded && <CompDetail comp={comp} />}
    </div>
  );
}

const TIER_ORDER = ["S", "A", "B", "C"];

export function CompListPage() {
  const [comps, setComps] = useState<CompData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAllComps()
      .then(setComps)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="comps-page"><p className="comps-loading">読み込み中...</p></div>;
  if (error)   return <div className="comps-page"><p className="error-text">エラー: {error}</p></div>;

  const byTier = TIER_ORDER.reduce<Record<string, CompData[]>>((acc, t) => {
    acc[t] = comps.filter((c) => c.tier === t);
    return acc;
  }, {});

  return (
    <div className="comps-page">
      <div className="comps-page-header">
        <h2>構成一覧 <span className="comps-set-tag">Set 17 Space Gods</span></h2>
        <p className="comps-page-sub">クリックで詳細（配置ユニット・アイテム・序盤ボード・使いどき）を表示</p>
      </div>

      {TIER_ORDER.filter((t) => byTier[t].length > 0).map((tier) => (
        <section key={tier} className="tier-section">
          <div className="tier-section-header">
            <TierBadge tier={tier} />
            <span className="tier-section-label">ティア</span>
          </div>
          <div className="tier-comp-list">
            {byTier[tier].map((comp) => (
              <CompRow key={comp.id} comp={comp} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
