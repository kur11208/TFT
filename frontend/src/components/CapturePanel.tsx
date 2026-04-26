import React, { useEffect, useRef, useState, useCallback } from "react";
import type { AnalyzeRequest } from "../types";
import {
  captureScreen,
  getCaptureStatus,
  getCapturePreview,
  type CaptureResult,
} from "../api/capture";
import { API_BASE } from "../config";

interface Props {
  currentState: AnalyzeRequest;
  onCaptured: (req: AnalyzeRequest) => void;
}

type OcrStatus = "idle" | "capturing" | "ok" | "error";
type GameState = "unknown" | "running" | "stopped";

export function CapturePanel({ currentState, onCaptured }: Props) {
  // OCR availability
  const [ocrReady, setOcrReady] = useState<boolean | null>(null);

  // Game process detection via SSE
  const [gameState, setGameState] = useState<GameState>("unknown");
  const [gameProcess, setGameProcess] = useState<string | null>(null);

  // Capture state
  const [captureStatus, setCaptureStatus] = useState<OcrStatus>("idle");
  const [lastResult, setLastResult] = useState<CaptureResult | null>(null);
  const [autoCapture, setAutoCapture] = useState(false);
  const [intervalSec, setIntervalSec] = useState(3);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Preview
  const [showPreview, setShowPreview] = useState(false);
  const [previewB64, setPreviewB64] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoRef = useRef(autoCapture);
  const stateRef = useRef(currentState);
  autoRef.current = autoCapture;
  stateRef.current = currentState;

  // Check OCR on mount
  useEffect(() => {
    getCaptureStatus()
      .then((s) => setOcrReady(s.ocr_ready))
      .catch(() => setOcrReady(false));
  }, []);

  // SSE: watch game process
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/game/events`);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as { running: boolean; process: string | null };
        setGameState(data.running ? "running" : "stopped");
        setGameProcess(data.process);

        // Game started → enable auto-capture automatically
        if (data.running && !autoRef.current) {
          setAutoCapture(true);
        }
        // Game ended → stop auto-capture
        if (!data.running && autoRef.current) {
          setAutoCapture(false);
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setGameState("unknown");
    };

    return () => es.close();
  }, []);

  // Auto-capture timer
  const doCapture = useCallback(async () => {
    if (!ocrReady) return;
    setCaptureStatus("capturing");
    setErrorMsg(null);
    try {
      const result = await captureScreen(stateRef.current, false);
      setLastResult(result);
      onCaptured(result.state);
      setCaptureStatus("ok");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "キャプチャ失敗");
      setCaptureStatus("error");
    }
  }, [ocrReady, onCaptured]);

  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (autoCapture && ocrReady) {
      doCapture(); // immediate
      timerRef.current = setInterval(doCapture, intervalSec * 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [autoCapture, intervalSec, ocrReady]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleAuto = () => setAutoCapture((v) => !v);

  const doPreview = async () => {
    setShowPreview(true);
    setPreviewB64(null);
    try {
      const b64 = await getCapturePreview();
      setPreviewB64(b64);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "プレビュー失敗");
    }
  };

  const confColor = (v: number) =>
    v >= 0.7 ? "#4ade80" : v >= 0.4 ? "#facc15" : "#f87171";

  // ---- game indicator ----
  const gameLabel =
    gameState === "running"
      ? `ゲーム検出: ${gameProcess ?? "League of Legends"}`
      : gameState === "stopped"
      ? "ゲーム未起動"
      : "監視中...";

  const gameDot =
    gameState === "running" ? "dot-green" : gameState === "stopped" ? "dot-red" : "dot-gray";

  return (
    <div className="capture-panel">
      <div className="capture-header">
        <h2>リアルタイムキャプチャ</h2>
        <div className={`ocr-badge ${ocrReady === true ? "ok" : ocrReady === false ? "ng" : "checking"}`}>
          {ocrReady === null ? "確認中" : ocrReady ? "OCR Ready" : "OCR 未設定"}
        </div>
      </div>

      {/* Game process status */}
      <div className="game-status-bar">
        <span className={`status-dot ${gameDot}`} />
        <span className="game-label">{gameLabel}</span>
        {gameState === "running" && autoCapture && (
          <span className="auto-badge">自動キャプチャ中</span>
        )}
      </div>

      {ocrReady === false && (
        <div className="capture-warning">
          <strong>Tesseract OCR が見つかりません。</strong><br />
          <a href="https://github.com/UB-Mannheim/tesseract/wiki" target="_blank" rel="noreferrer">
            こちら
          </a>
          からインストール後、バックエンドを再起動してください。<br />
          <code>pip install pytesseract</code> も必要です。
        </div>
      )}

      {/* Controls */}
      <div className="capture-controls">
        <button
          className="btn-capture"
          onClick={doCapture}
          disabled={!ocrReady || captureStatus === "capturing"}
        >
          {captureStatus === "capturing" ? "キャプチャ中..." : "今すぐキャプチャ"}
        </button>

        <div className="auto-row">
          <button
            className={`btn-auto ${autoCapture ? "active" : ""}`}
            onClick={toggleAuto}
            disabled={!ocrReady}
          >
            {autoCapture ? "■ 自動停止" : "▶ 自動キャプチャ"}
          </button>
          <label className="interval-label">
            間隔
            <input
              type="number"
              min={1}
              max={30}
              value={intervalSec}
              onChange={(e) => setIntervalSec(Math.max(1, Number(e.target.value)))}
              className="interval-input"
            />
            秒
          </label>
        </div>

        <button className="btn-preview" onClick={doPreview} disabled={!ocrReady}>
          領域プレビュー
        </button>
      </div>

      {/* Last capture summary */}
      {captureStatus === "ok" && lastResult && (
        <div className="capture-result-summary">
          <div className="capture-ts">
            最終取得: {new Date(lastResult.timestamp).toLocaleTimeString()}
          </div>
          <div className="conf-grid">
            {Object.entries(lastResult.confidence).map(([k, v]) => (
              <div key={k} className="conf-item">
                <span className="conf-key">{k}</span>
                <span className="conf-raw">{lastResult.raw_ocr[k] ?? "-"}</span>
                <span className="conf-val" style={{ color: confColor(v) }}>
                  {Math.round(v * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {captureStatus === "error" && errorMsg && (
        <p className="capture-error">{errorMsg}</p>
      )}

      {/* Preview modal */}
      {showPreview && (
        <div className="preview-overlay" onClick={() => setShowPreview(false)}>
          <div className="preview-modal" onClick={(e) => e.stopPropagation()}>
            <div className="preview-modal-header">
              <span>キャプチャ領域プレビュー</span>
              <button onClick={() => setShowPreview(false)}>×</button>
            </div>
            {previewB64 ? (
              <img
                src={`data:image/png;base64,${previewB64}`}
                alt="capture preview"
                style={{ maxWidth: "100%", display: "block" }}
              />
            ) : (
              <p style={{ padding: "20px", color: "#94a3b8" }}>読み込み中...</p>
            )}
            <p className="preview-hint">
              ボックスがズレる場合は
              <code>backend/app/data/current/regions.json</code>
              の座標を調整してください。
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
