import React, { useEffect, useRef, useState, useCallback } from "react";
import { API_BASE as API } from "../config";

type Region = { x: number; y: number; w: number; h: number; desc?: string };
type RegionsData = {
  note?: string;
  base_width?: number;
  base_height?: number;
  regions: Record<string, Region>;
};
type CaptureResult = {
  state: {
    stage: string; level: number; hp: number; gold: number;
    board: { name: string; stars: number }[];
    bench: { name: string; stars: number }[];
    shop:  { name: string; stars: number }[];
    items: string[];
    augments: string[];
  };
  raw_ocr: Record<string, string>;
  confidence: Record<string, number>;
  preview_b64: string;
};

const GROUPS: [string, string][] = [
  ["basic",          "基本 (stage / level / hp / gold)"],
  ["portrait_board", "ポートレート ボード"],
  ["portrait_bench", "ポートレート ベンチ"],
  ["portrait_shop",  "ポートレート ショップ"],
  ["board_text",     "ボード テキスト"],
  ["bench_text",     "ベンチ テキスト"],
  ["shop_text",      "ショップ テキスト"],
  ["augment",        "オーグメント / 神"],
  ["item",           "アイテム"],
];

function classifyKey(key: string): string {
  if (["stage", "level", "hp", "gold"].includes(key)) return "basic";
  if (key.startsWith("portrait_board"))                return "portrait_board";
  if (key.startsWith("portrait_bench"))                return "portrait_bench";
  if (key.startsWith("portrait_shop"))                 return "portrait_shop";
  if (key.startsWith("board_"))                        return "board_text";
  if (key.startsWith("bench_"))                        return "bench_text";
  if (key.startsWith("shop_"))                         return "shop_text";
  if (key.startsWith("aug_") || key.startsWith("god_")) return "augment";
  if (key.startsWith("item_"))                         return "item";
  return "basic";
}

function ConfBadge({ v }: { v: number }) {
  const cls = v >= 0.7 ? "conf-ok" : v >= 0.45 ? "conf-mid" : "conf-bad";
  return <span className={`conf-badge ${cls}`}>{(v * 100).toFixed(0)}%</span>;
}

export function CalibrationPage() {
  const [regionsData, setRegionsData] = useState<RegionsData>({ regions: {} });
  const [previewB64, setPreview]      = useState<string>("");
  const [selectedKey, setSelected]    = useState<string>("");
  const [cursor, setCursor]           = useState<{ x: number; y: number } | null>(null);
  const [screenW, setScreenW]         = useState(1920);
  const [saving, setSaving]           = useState(false);
  const [capturing, setCapturing]     = useState(false);
  const [testing, setTesting]         = useState(false);
  const [savedMsg, setSavedMsg]       = useState("");
  const [mode, setMode]               = useState<"calibrate" | "recognize">("calibrate");
  const [captureResult, setCaptureResult] = useState<CaptureResult | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // ---- fetch helpers ----
  const fetchRegions = useCallback(async () => {
    try {
      const r = await fetch(`${API}/capture/regions`);
      const d = await r.json();
      setRegionsData(d);
    } catch {}
  }, []);

  const fetchScreenW = useCallback(async () => {
    try {
      const r = await fetch(`${API}/debug/screen`);
      const d = await r.json();
      const m = (d.screen_size ?? "1920x1080").match(/(\d+)/);
      if (m) setScreenW(parseInt(m[1]));
    } catch {}
  }, []);

  // 座標確認スクショ（OCRなし・リージョン枠のみ）
  const fetchPreview = useCallback(async () => {
    setCapturing(true);
    setMode("calibrate");
    try {
      const r = await fetch(`${API}/capture/preview`);
      const d = await r.json();
      setPreview(d.image_b64 ?? "");
    } catch {}
    finally { setCapturing(false); }
  }, []);

  // 認識テスト（OCR実行 + 結果付き画像）
  const runRecognitionTest = useCallback(async () => {
    setTesting(true);
    setMode("recognize");
    setCaptureResult(null);
    try {
      const r = await fetch(`${API}/capture`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include_preview: true }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d: CaptureResult = await r.json();
      setCaptureResult(d);
      setPreview(d.preview_b64 ?? "");
    } catch {}
    finally { setTesting(false); }
  }, []);

  useEffect(() => { fetchRegions(); fetchPreview(); fetchScreenW(); },
    [fetchRegions, fetchPreview, fetchScreenW]);

  // ---- image click → original coords ----
  const handleImageClick = useCallback((e: React.MouseEvent<HTMLImageElement>) => {
    if (mode !== "calibrate") return; // 認識モードではクリック無効
    const img = imgRef.current;
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const px = (e.clientX - rect.left) * (img.naturalWidth  / rect.width);
    const py = (e.clientY - rect.top)  * (img.naturalHeight / rect.height);
    const scale = screenW / (img.naturalWidth || screenW);
    setCursor({ x: Math.round(px * scale), y: Math.round(py * scale) });
  }, [screenW, mode]);

  // ---- region field edit ----
  const updateField = (field: keyof Region, raw: string) => {
    const val = parseInt(raw, 10);
    if (isNaN(val) || !selectedKey) return;
    setRegionsData(prev => ({
      ...prev,
      regions: {
        ...prev.regions,
        [selectedKey]: { ...prev.regions[selectedKey], [field]: val },
      },
    }));
  };

  // ---- save ----
  const handleSave = async () => {
    setSaving(true);
    setSavedMsg("");
    try {
      await fetch(`${API}/capture/regions`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(regionsData),
      });
      setSavedMsg("保存しました");
      await fetchPreview();
    } catch { setSavedMsg("保存失敗"); }
    finally { setSaving(false); }
  };

  // ---- grouped region keys ----
  const grouped: Record<string, string[]> = {};
  for (const key of Object.keys(regionsData.regions)) {
    const g = classifyKey(key);
    (grouped[g] ??= []).push(key);
  }
  Object.values(grouped).forEach(arr => arr.sort());

  const sel = selectedKey ? regionsData.regions[selectedKey] : null;
  const cr  = captureResult;

  return (
    <div className="calib-root">
      {/* ===== toolbar ===== */}
      <div className="calib-toolbar">
        <button
          className={`calib-btn ${mode === "calibrate" ? "calib-mode-active" : ""}`}
          onClick={fetchPreview}
          disabled={capturing}
        >
          {capturing ? "キャプチャ中…" : "📷 座標確認"}
        </button>
        <button
          className={`calib-btn calib-test-btn ${mode === "recognize" ? "calib-mode-active" : ""}`}
          onClick={runRecognitionTest}
          disabled={testing}
        >
          {testing ? "認識中…" : "🔍 認識テスト"}
        </button>

        {mode === "calibrate" && (
          <>
            <div className="calib-divider" />
            <button className="calib-btn calib-save" onClick={handleSave} disabled={saving}>
              {saving ? "保存中…" : "💾 保存して反映"}
            </button>
            {savedMsg && <span className="calib-saved">{savedMsg}</span>}
            <span className="calib-hint">画像をクリック → 座標取得</span>
          </>
        )}

        {cursor && mode === "calibrate" && (
          <span className="calib-cursor-info">
            x={cursor.x}, y={cursor.y}
            {sel && (
              <button className="calib-apply-btn" onClick={() => {
                setRegionsData(prev => ({
                  ...prev,
                  regions: {
                    ...prev.regions,
                    [selectedKey]: { ...prev.regions[selectedKey], x: cursor.x, y: cursor.y },
                  },
                }));
                setCursor(null);
              }}>→ 左上に適用</button>
            )}
            <button className="calib-cursor-close" onClick={() => setCursor(null)}>✕</button>
          </span>
        )}
      </div>

      <div className="calib-body">
        {/* ===== preview image ===== */}
        <div className="calib-img-col">
          {previewB64 ? (
            <img
              ref={imgRef}
              src={`data:image/png;base64,${previewB64}`}
              className={`calib-img ${mode === "calibrate" ? "calib-img-crosshair" : ""}`}
              onClick={handleImageClick}
              alt="preview"
              title={mode === "calibrate" ? "クリックして座標を取得" : "認識結果 (右パネルで詳細確認)"}
            />
          ) : (
            <div className="calib-no-img">ボタンを押してゲーム画面を取得してください</div>
          )}
        </div>

        {/* ===== right panel ===== */}
        <div className="calib-right">

          {/* ---- 認識結果パネル ---- */}
          {mode === "recognize" && cr && (
            <div className="calib-recog-panel">
              <div className="calib-recog-title">認識結果</div>

              {/* 数値 */}
              <div className="calib-recog-stats">
                {[
                  ["ステージ", cr.state.stage,  cr.confidence["stage"]],
                  ["レベル",   cr.state.level,  cr.confidence["level"]],
                  ["HP",       cr.state.hp,     cr.confidence["hp"]],
                  ["Gold",     cr.state.gold,   cr.confidence["gold"]],
                ].map(([label, val, conf]) => (
                  <div key={String(label)} className="calib-recog-stat">
                    <span className="calib-recog-label">{label}</span>
                    <span className="calib-recog-val">{String(val ?? "—")}</span>
                    {conf != null && <ConfBadge v={conf as number} />}
                  </div>
                ))}
              </div>

              {/* ボード */}
              <UnitGroup label="ボード" units={cr.state.board}
                rawOcr={cr.raw_ocr} conf={cr.confidence} prefix="portrait_board" />

              {/* ベンチ */}
              <UnitGroup label="ベンチ" units={cr.state.bench}
                rawOcr={cr.raw_ocr} conf={cr.confidence} prefix="portrait_bench" />

              {/* ショップ */}
              <UnitGroup label="ショップ" units={cr.state.shop}
                rawOcr={cr.raw_ocr} conf={cr.confidence} prefix="portrait_shop" />

              {/* アイテム */}
              {cr.state.items.length > 0 && (
                <div className="calib-recog-group">
                  <div className="calib-recog-group-hdr">アイテム</div>
                  <div className="calib-recog-items">
                    {cr.state.items.map((item, i) => (
                      <span key={i} className="calib-item-chip">{item}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* 未認識スロット一覧（conf低い or null のリージョン） */}
              <LowConfList rawOcr={cr.raw_ocr} conf={cr.confidence} />
            </div>
          )}

          {mode === "recognize" && !cr && !testing && (
            <div className="calib-no-img" style={{ padding: 20, fontSize: 12 }}>
              「認識テスト」を押してください
            </div>
          )}

          {/* ---- 座標調整パネル (calibrate mode) ---- */}
          {mode === "calibrate" && (
            <>
              {selectedKey && sel && (
                <div className="calib-editor">
                  <div className="calib-editor-name">{selectedKey}</div>
                  {sel.desc && <div className="calib-editor-desc">{sel.desc}</div>}
                  <div className="calib-fields">
                    {(["x", "y", "w", "h"] as const).map(f => (
                      <label key={f} className="calib-field">
                        <span className="calib-field-label">{f}</span>
                        <input
                          type="number"
                          className="calib-field-input"
                          value={sel[f]}
                          onChange={e => updateField(f, e.target.value)}
                        />
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="calib-list">
                {GROUPS.map(([gk, glabel]) => {
                  const keys = grouped[gk];
                  if (!keys?.length) return null;
                  return (
                    <details key={gk} className="calib-group"
                      open={!!(selectedKey && keys.includes(selectedKey))}>
                      <summary className="calib-group-header">{glabel}</summary>
                      {keys.map(key => (
                        <button
                          key={key}
                          className={`calib-region-btn ${selectedKey === key ? "calib-region-active" : ""}`}
                          onClick={() => setSelected(prev => prev === key ? "" : key)}
                        >
                          <span className="calib-rk">{key}</span>
                          <span className="calib-rv">
                            {regionsData.regions[key]
                              ? `(${regionsData.regions[key].x},${regionsData.regions[key].y}) ${regionsData.regions[key].w}×${regionsData.regions[key].h}`
                              : ""}
                          </span>
                        </button>
                      ))}
                    </details>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---- helper sub-components ----

function UnitGroup({ label, units, rawOcr, conf, prefix }: {
  label: string;
  units: { name: string; stars: number }[];
  rawOcr: Record<string, string>;
  conf: Record<string, number>;
  prefix: string;
}) {
  // Collect all slots that were attempted (by prefix)
  const slots = Object.entries(rawOcr)
    .filter(([k]) => k.startsWith(prefix))
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="calib-recog-group">
      <div className="calib-recog-group-hdr">
        {label} <span className="calib-recog-count">({units.length}体)</span>
      </div>
      <div className="calib-unit-grid">
        {slots.map(([key, name]) => {
          const c = conf[key] ?? 0;
          return (
            <div key={key} className={`calib-unit-chip ${!name ? "calib-unit-empty" : c < 0.45 ? "calib-unit-low" : ""}`}>
              <span className="calib-unit-name">{name || "—"}</span>
              {name && <ConfBadge v={c} />}
            </div>
          );
        })}
        {slots.length === 0 && units.map((u, i) => (
          <div key={i} className="calib-unit-chip">
            <span className="calib-unit-name">{u.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LowConfList({ rawOcr, conf }: {
  rawOcr: Record<string, string>;
  conf: Record<string, number>;
}) {
  const low = Object.entries(conf)
    .filter(([k, v]) => rawOcr[k] && v < 0.5)
    .sort(([, a], [, b]) => a - b)
    .slice(0, 10);

  if (!low.length) return null;
  return (
    <div className="calib-recog-group">
      <div className="calib-recog-group-hdr calib-warn-hdr">信頼度が低いスロット</div>
      {low.map(([key, v]) => (
        <div key={key} className="calib-low-item">
          <span className="calib-low-key">{key}</span>
          <span className="calib-low-val">{rawOcr[key]}</span>
          <ConfBadge v={v} />
        </div>
      ))}
    </div>
  );
}
