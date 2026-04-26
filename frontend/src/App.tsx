import React, { useCallback, useState } from "react";

import type { AnalyzeRequest, AnalyzeResponse } from "./types";
import { analyzeBoard } from "./api/analyze";
import { CalibrationPage } from "./components/CalibrationPage";
import { CapturePanel } from "./components/CapturePanel";
import { CompListPage } from "./components/CompListPage";
import { ForgeOverlayPage } from "./components/ForgeOverlayPage";
import { GodBoonOverlayPage } from "./components/GodBoonOverlayPage";
import { GodsPickerOverlayPage } from "./components/GodsPickerOverlayPage";
import { InputPanel } from "./components/InputPanel";
import { OverlayPageV2 } from "./components/OverlayPageV2";
import { ResultPanel } from "./components/ResultPanel";
import { AugmentOverlayPage } from "./components/AugmentOverlayPage";

const LS_KEY = "tft_analysis_result";

const EMPTY_REQUEST: AnalyzeRequest = {
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

const SAMPLE_REQUEST: AnalyzeRequest = {
  patch: "current",
  stage: "3-2",
  level: 6,
  hp: 78,
  gold: 38,
  streak: 2,
  board: [
    { name: "Front Tank", stars: 2, tags: ["Guardian", "Tank", "Frontline"] },
    { name: "Second Tank", stars: 1, tags: ["Bastion", "Tank", "Frontline"] },
    { name: "Main Carry", stars: 2, tags: ["Carry", "Sniper", "Backline"] },
    { name: "Support", stars: 1, tags: ["Invoker", "Support", "Backline"] },
    { name: "Flex Unit", stars: 1, tags: ["Bruiser", "Frontline"] },
  ],
  bench: [
    { name: "Main Carry", stars: 1, tags: ["Carry", "Sniper", "Backline"] },
  ],
  shop: [
    { name: "Front Tank", stars: 1, tags: ["Guardian", "Tank", "Frontline"] },
    { name: "Backline DPS", stars: 1, tags: ["Carry", "Rapidfire", "Backline"] },
    { name: "Trait Bot", stars: 1, tags: ["Invoker", "Support"] },
  ],
  items: ["Rod", "Tear", "Vest", "Belt"],
  augments: ["Economy Augment"],
  notes: "前衛を固めつつ、後衛キャリーにアイテムを寄せたい。",
};

const searchParams = new URLSearchParams(window.location.search);
const IS_OVERLAY = Boolean(searchParams.get("overlay"));
const PAGE = searchParams.get("page");

function openOverlay(tab?: string) {
  const base = `${window.location.origin}${window.location.pathname}?overlay=2`;
  const url = tab ? `${base}&tab=${tab}` : base;
  const width = 480;
  const height = 720;
  const left = Math.max(16, window.screen.availWidth - width - 20);
  const top = 60;
  window.open(
    url,
    tab ? `tft-overlay-${tab}` : "tft-overlay",
    `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=no,status=no,toolbar=no,menubar=no,location=no`,
  );
}

export default function App() {
  if (PAGE === "augment") return <AugmentOverlayPage />;
  if (PAGE === "forge") return <ForgeOverlayPage />;
  if (PAGE === "gods") return <GodsPickerOverlayPage />;
  if (PAGE === "godboon") return <GodBoonOverlayPage />;
  if (IS_OVERLAY) return <OverlayPageV2 />;

  const [request, setRequest] = useState<AnalyzeRequest>(EMPTY_REQUEST);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<"manual" | "capture" | "comps" | "calibration">("capture");

  const handleAnalyze = useCallback(async (req?: AnalyzeRequest) => {
    const target = req ?? request;
    setLoading(true);
    setError(null);
    try {
      const response = await analyzeBoard(target);
      setResult(response);
      localStorage.setItem(LS_KEY, JSON.stringify(response));
    } catch (e) {
      setError(e instanceof Error ? e.message : "不明なエラー");
    } finally {
      setLoading(false);
    }
  }, [request]);

  const handleLoadSample = useCallback(() => {
    setRequest(SAMPLE_REQUEST);
    setResult(null);
    setError(null);
  }, []);

  const handleCaptured = useCallback((captured: AnalyzeRequest) => {
    setRequest(captured);
    handleAnalyze(captured);
  }, [handleAnalyze]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>TFT Advisor</h1>
        <span className="header-sub">盤面分析と意思決定支援</span>

        <div className="tab-switch">
          <button className={tab === "capture" ? "tab active" : "tab"} onClick={() => setTab("capture")}>
            自動キャプチャ
          </button>
          <button className={tab === "manual" ? "tab active" : "tab"} onClick={() => setTab("manual")}>
            手動入力
          </button>
          <button className={tab === "comps" ? "tab active" : "tab"} onClick={() => setTab("comps")}>
            構成一覧
          </button>
          <button className={tab === "calibration" ? "tab active" : "tab"} onClick={() => setTab("calibration")}>
            座標調整
          </button>
        </div>

        <div className="overlay-btn-group">
          <button className="btn-overlay-launch" onClick={() => openOverlay()} title="通常オーバーレイを開く">
            オーバーレイ
          </button>
          <button className="btn-overlay-launch" onClick={() => openOverlay("placement")} title="配置アドバイス用オーバーレイ">
            配置
          </button>
          <button className="btn-overlay-launch" onClick={() => openOverlay("augments")} title="オーグメント選択用オーバーレイ">
            オーグメント
          </button>
        </div>
      </header>

      {tab === "comps" && (
        <main className="app-body-full">
          <CompListPage />
        </main>
      )}

      {tab === "calibration" && (
        <main className="app-body-full">
          <CalibrationPage />
        </main>
      )}

      <main className="app-body" style={{ display: tab === "comps" || tab === "calibration" ? "none" : undefined }}>
        <div className="left-col">
          {tab === "capture" && (
            <CapturePanel currentState={request} onCaptured={handleCaptured} />
          )}

          <div style={{ display: tab === "manual" ? "block" : "none" }}>
            <InputPanel
              request={request}
              onChange={setRequest}
              onAnalyze={() => handleAnalyze()}
              onLoadSample={handleLoadSample}
              loading={loading}
            />
          </div>

          {tab === "capture" && (
            <div className="state-summary">
              <div className="state-summary-header">
                <span>現在の盤面概要</span>
                <button className="btn-small" onClick={() => setTab("manual")}>
                  手動で調整
                </button>
              </div>

              <div className="state-grid">
                <span className="sk">ステージ</span><span className="sv">{request.stage}</span>
                <span className="sk">レベル</span><span className="sv">{request.level}</span>
                <span className="sk">HP</span><span className="sv">{request.hp}</span>
                <span className="sk">Gold</span><span className="sv">{request.gold}</span>
                <span className="sk">盤面</span>
                <span className="sv">
                  {request.board.length > 0
                    ? request.board.map((unit) => `${unit.name}${"★".repeat(unit.stars)}`).join(", ")
                    : "未入力"}
                </span>
                <span className="sk">ショップ</span>
                <span className="sv">
                  {request.shop.length > 0 ? request.shop.map((unit) => unit.name).join(", ") : "未入力"}
                </span>
              </div>

              <button className="btn-analyze" onClick={() => handleAnalyze()} disabled={loading} style={{ marginTop: 8 }}>
                {loading ? "分析中..." : "Analyze"}
              </button>
            </div>
          )}
        </div>

        <ResultPanel result={result} request={request} error={error} loading={loading} />
      </main>
    </div>
  );
}
