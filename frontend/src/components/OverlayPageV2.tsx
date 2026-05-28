import React, { useCallback, useEffect, useRef, useState } from "react";

import type { AnalyzeRequest, AnalyzeResponse, SituationAction } from "../types";
import { API_BASE as API } from "../config";
import {
  clearSelectionContext,
  DEFAULT_ANALYZE_REQUEST,
  normalizeAnalyzeRequest,
  normalizeStage,
  readOverlayContext,
  writeSelectionContext,
  writeOverlayContext,
} from "../utils/analyzeState";
import {
  clearOverlayLiveSnapshot,
  writeOverlayLiveSnapshot,
} from "../utils/overlayLive";
import { buildShopHighlights, shopActionLabel } from "../utils/shopHighlights";

type Bridge = {
  mouseEnter(): void;
  mouseLeave(): void;
  minimize(): void;
  close(): void;
  setOverlaySize(width: number, height: number): void;
  dragStart(): void;
  dragMove(): void;
  dragEnd(): void;
  showAugment(stage: string): void;
  hideAugment(): void;
  showForge(): void;
  hideForge(): void;
  showGods(stage: string): void;
  hideGods(): void;
  showGodBoon(): void;
  hideGodBoon(): void;
};

type SourceState = "idle" | "ok" | "miss" | "error";

type SourceMeta = {
  gep: SourceState;
  lcu: SourceState;
  ocr: SourceState;
  active: string;
};

type DebugCapture = {
  summary: Record<string, unknown>;
  low_confidence: Record<string, number>;
  png: string;
  timestamp: string;
  label: string;
};

type GepStreamPayload = {
  in_game?: boolean;
  state?: Partial<AnalyzeRequest>;
  revision?: number;
};

type AutoSaveStatus = {
  enabled: boolean;
  interval_sec: number;
  only_normal: boolean;
  only_in_game: boolean;
  last_attempt_at: number;
  last_saved_at: number;
  last_saved_path: string;
  last_screen_state: string;
  last_skip_reason: string;
  save_count: number;
  revision: number;
  output_dir: string;
};

type AutoSaveConfigPatch = {
  enabled?: boolean;
  interval_sec?: number;
  only_normal?: boolean;
  only_in_game?: boolean;
};

type ScreenStatePayload = {
  state?: string;
  stage?: string;
  selection_type?: "augment" | "god" | "forge" | "godboon";
  augments?: string[];
  gods?: string[];
  forge_items?: string[];
  boons?: string[];
};

type PopupPage = "augment" | "gods" | "forge" | "godboon";

const electronBridge = (window as { electronBridge?: Bridge }).electronBridge;
const isInIframe = window.self !== window.top;

const owBridge: Bridge = {
  mouseEnter: () => {},
  mouseLeave: () => {},
  minimize: () => window.parent.postMessage({ type: "ow:minimize" }, "*"),
  close: () => window.parent.postMessage({ type: "ow:close" }, "*"),
  setOverlaySize: (width, height) => window.parent.postMessage({ type: "ow:setOverlaySize", width, height }, "*"),
  dragStart: () => window.parent.postMessage({ type: "ow:dragMove" }, "*"),
  dragMove: () => {},
  dragEnd: () => {},
  showAugment: (stage) => window.parent.postMessage({ type: "ow:showAugment", stage }, "*"),
  hideAugment: () => window.parent.postMessage({ type: "ow:hideAugment" }, "*"),
  showForge: () => window.parent.postMessage({ type: "ow:showForge" }, "*"),
  hideForge: () => window.parent.postMessage({ type: "ow:hideForge" }, "*"),
  showGods: (stage) => window.parent.postMessage({ type: "ow:showGods", stage }, "*"),
  hideGods: () => window.parent.postMessage({ type: "ow:hideGods" }, "*"),
  showGodBoon: () => window.parent.postMessage({ type: "ow:showGodBoon" }, "*"),
  hideGodBoon: () => window.parent.postMessage({ type: "ow:hideGodBoon" }, "*"),
};

const bridge = electronBridge ?? (isInIframe ? owBridge : undefined);

const PRIORITY_COLOR: Record<SituationAction["priority"], string> = {
  urgent: "#f87171",
  high: "#facc15",
  medium: "#94a3b8",
};

const SOURCE_LABEL: Record<SourceState, string> = {
  idle: "待機",
  ok: "OK",
  miss: "なし",
  error: "失敗",
};

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = 8000): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("request timeout");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

const POPUP_BASE_SCREEN_WIDTH = 1920;
const POPUP_SAFE_LEFT_EDGE: Record<PopupPage, number> = {
  augment: 422,
  forge: 422,
  gods: 696,
  godboon: 422,
};

function buildPopupUrl(page: string, stage: string): string {
  const url = new URL(window.location.href);
  url.search = "";
  url.searchParams.set("page", page);
  if (stage) {
    url.searchParams.set("stage", stage);
  }
  return url.toString();
}

function getBrowserPopupFrame(page: PopupPage): { width: number; height: number; left: number; top: number } {
  const availWidth = window.screen?.availWidth || 1920;
  const availHeight = window.screen?.availHeight || 1080;
  const left = 24;
  const top = page === "forge" ? 96 : 88;
  const maxWidth = Math.floor((POPUP_SAFE_LEFT_EDGE[page] * availWidth) / POPUP_BASE_SCREEN_WIDTH) - left - 18;

  let width = page === "gods" ? 360 : page === "forge" ? 360 : 380;
  let height = page === "gods" ? 500 : page === "forge" ? 480 : 460;

  if (Number.isFinite(maxWidth) && maxWidth > 0) {
    width = Math.min(width, maxWidth);
  }

  const minWidth = page === "gods" ? 240 : 220;
  const minHeight = page === "gods" ? 380 : page === "forge" ? 360 : 340;
  width = Math.max(minWidth, Math.min(width, availWidth - left - 12));
  height = Math.max(minHeight, Math.min(height, availHeight - top - 24));

  return { width, height, left, top };
}

function isAugmentStage(stage: string): boolean {
  return stage === "2-1" || stage === "3-2" || stage === "4-2";
}

function isGodStage(stage: string): boolean {
  return stage === "2-4" || stage === "3-4" || stage === "4-4";
}

function isSelectionPopupAllowed(
  page: PopupPage,
  stage: string,
  counts: { augments: number; gods: number; forgeItems: number; boons: number },
): boolean {
  if (page === "augment") return isAugmentStage(stage) && counts.augments >= 2;
  if (page === "gods") return counts.gods >= 1 || isGodStage(stage);
  if (page === "forge") return counts.forgeItems >= 2;
  if (page === "godboon") return stage === "4-7";
  return false;
}

function sourceChipClass(state: SourceState): string {
  return `v2-source-chip v2-source-${state}`;
}

function mergeAnalyzeState(
  current: AnalyzeRequest,
  patch?: Partial<AnalyzeRequest> | null,
): AnalyzeRequest {
  if (!patch) return current;

  return normalizeAnalyzeRequest(
    {
      ...current,
      ...patch,
      board: Array.isArray(patch.board) && patch.board.length > 0 ? patch.board : current.board,
      bench: Array.isArray(patch.bench) && patch.bench.length > 0 ? patch.bench : current.bench,
      shop: Array.isArray(patch.shop) && patch.shop.length > 0 ? patch.shop : current.shop,
      items: Array.isArray(patch.items) && patch.items.length > 0 ? patch.items : current.items,
      augments: Array.isArray(patch.augments) && patch.augments.length > 0 ? patch.augments : current.augments,
    },
    current,
  );
}

export function OverlayPageV2() {
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [stage, setStage] = useState(DEFAULT_ANALYZE_REQUEST.stage);
  const [level, setLevel] = useState(DEFAULT_ANALYZE_REQUEST.level);
  const [hp, setHp] = useState(DEFAULT_ANALYZE_REQUEST.hp);
  const [gold, setGold] = useState(DEFAULT_ANALYZE_REQUEST.gold);
  const [inGame, setInGame] = useState(false);
  const [autoMode, setAutoMode] = useState(true);
  const [busy, setBusy] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [lastTs, setLastTs] = useState("");
  const [minimized, setMinimized] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [sourceMeta, setSourceMeta] = useState<SourceMeta>({
    gep: "idle",
    lcu: "idle",
    ocr: "idle",
    active: "未取得",
  });
  const [debugSaving, setDebugSaving] = useState(false);
  const [debugResult, setDebugResult] = useState<DebugCapture | null>(null);
  const [lastCaptureTs, setLastCaptureTs] = useState("");
  const [autoSaveStatus, setAutoSaveStatus] = useState<AutoSaveStatus | null>(null);
  const [autoSaveBusy, setAutoSaveBusy] = useState(false);

  const rootRef = useRef<HTMLDivElement>(null);
  const autoRef = useRef(autoMode);
  const inGameRef = useRef(inGame);
  const busyRef = useRef(busy);
  const analyzeTimerRef = useRef<number | null>(null);
  const queuedAnalyzeRef = useRef(false);
  const lastGepSignatureRef = useRef("");
  const lastStateRef = useRef<AnalyzeRequest>(DEFAULT_ANALYZE_REQUEST);
  const resultRef = useRef<AnalyzeResponse | null>(null);
  const popupWindowsRef = useRef<Record<PopupPage, Window | null>>({
    augment: null,
    gods: null,
    forge: null,
    godboon: null,
  });
  const activeSelectionPopupRef = useRef<PopupPage | null>(null);
  const autoManagedPopupRef = useRef(false);
  const lastSelectionSignatureRef = useRef("");
  const selectionMinimizedBeforeRef = useRef<boolean | null>(null);

  autoRef.current = autoMode;
  inGameRef.current = inGame;
  busyRef.current = busy;

  useEffect(() => {
    const stored = readOverlayContext();
    if (stored.stage) {
      setStage(normalizeStage(stored.stage, DEFAULT_ANALYZE_REQUEST.stage));
    }
    if (typeof stored.hp === "number") {
      setHp(stored.hp);
    }
  }, []);

  useEffect(() => {
    writeOverlayContext({ stage, hp });
  }, [hp, stage]);

  useEffect(() => () => {
    if (analyzeTimerRef.current !== null) {
      window.clearTimeout(analyzeTimerRef.current);
    }
    if (!bridge) {
      Object.values(popupWindowsRef.current).forEach((popup) => popup?.close());
    }
  }, []);

  useEffect(() => {
    if (!bridge?.setOverlaySize || !rootRef.current || typeof ResizeObserver === "undefined") {
      return;
    }

    const node = rootRef.current;
    let frameId = 0;
    let lastWidth = 0;
    let lastHeight = 0;

    const syncSize = () => {
      frameId = 0;
      const rect = node.getBoundingClientRect();
      const width = Math.ceil(rect.width);
      const height = Math.ceil(rect.height);

      if (width === lastWidth && height === lastHeight) {
        return;
      }

      lastWidth = width;
      lastHeight = height;
      bridge.setOverlaySize(width, height);
    };

    const scheduleSync = () => {
      if (frameId !== 0) return;
      frameId = window.requestAnimationFrame(syncSize);
    };

    const observer = new ResizeObserver(scheduleSync);
    observer.observe(node);
    scheduleSync();

    return () => {
      observer.disconnect();
      if (frameId !== 0) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [bridge]);

  const applyOverlayState = useCallback((nextState: AnalyzeRequest) => {
    lastStateRef.current = nextState;
    setStage(nextState.stage);
    setLevel(nextState.level);
    setHp(nextState.hp);
    setGold(nextState.gold);
    writeOverlayContext({ stage: nextState.stage, hp: nextState.hp, items: nextState.items });
    writeOverlayLiveSnapshot({
      updatedAt: Date.now(),
      inGame: inGameRef.current,
      state: nextState,
      result: resultRef.current,
    });
  }, []);

  useEffect(() => {
    if (!inGame) {
      lastStateRef.current = DEFAULT_ANALYZE_REQUEST;
      resultRef.current = null;
      clearOverlayLiveSnapshot();
    }
  }, [inGame]);

  const hidePopup = useCallback((page: PopupPage) => {
    if (bridge) {
      if (page === "augment") bridge.hideAugment();
      if (page === "gods") bridge.hideGods();
      if (page === "forge") bridge.hideForge();
      if (page === "godboon") bridge.hideGodBoon();
      return;
    }

    const popup = popupWindowsRef.current[page];
    if (popup && !popup.closed) {
      popup.close();
    }
    popupWindowsRef.current[page] = null;
  }, []);

  const hideSelectionPopups = useCallback((force = false) => {
    if (!force && !autoManagedPopupRef.current) return;

    (["augment", "gods", "forge", "godboon"] as PopupPage[]).forEach((page) => {
      hidePopup(page);
    });
    if (selectionMinimizedBeforeRef.current !== null) {
      setMinimized(selectionMinimizedBeforeRef.current);
      selectionMinimizedBeforeRef.current = null;
    }
    activeSelectionPopupRef.current = null;
    autoManagedPopupRef.current = false;
  }, [hidePopup]);

  const showPopup = useCallback((page: PopupPage, popupStage: string, mode: "auto" | "manual" = "manual") => {
    const { width, height, left, top } = getBrowserPopupFrame(page);

    hideSelectionPopups(true);
    if (selectionMinimizedBeforeRef.current === null) {
      selectionMinimizedBeforeRef.current = minimized;
    }
    setMinimized(true);
    activeSelectionPopupRef.current = page;
    autoManagedPopupRef.current = mode === "auto";

    if (bridge) {
      if (page === "augment") bridge.showAugment(popupStage);
      if (page === "gods") bridge.showGods(popupStage);
      if (page === "forge") bridge.showForge();
      if (page === "godboon") bridge.showGodBoon();
      return;
    }

    const popup = window.open(
      buildPopupUrl(page, popupStage),
      `tft-${page}`,
      `width=${width},height=${height},left=${left},top=${top},resizable=yes`,
    );
    popupWindowsRef.current[page] = popup;
  }, [hideSelectionPopups, minimized]);

  const checkGame = useCallback(async () => {
    try {
      const response = await fetchWithTimeout(`${API}/game/state`, {}, 3000);
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (data.in_game) {
        setInGame(true);
        return;
      }
    } catch {}

    try {
      const response = await fetchWithTimeout(`${API}/game/status`, {}, 3000);
      if (!response.ok) throw new Error();
      const data = await response.json();
      setInGame(Boolean(data.running));
    } catch {
      setInGame(false);
    }
  }, []);

  const analyze = useCallback(async () => {
    if (busyRef.current) {
      queuedAnalyzeRef.current = true;
      return;
    }
    queuedAnalyzeRef.current = false;

    busyRef.current = true;
    setBusy(true);
    setErrMsg(null);

    try {
      const stored = readOverlayContext();
      let state = normalizeAnalyzeRequest(
        {
          ...lastStateRef.current,
          stage,
          level,
          hp,
          gold,
          preferred_comp_id: stored.compId ?? null,
        },
        DEFAULT_ANALYZE_REQUEST,
      );

      const nextSourceMeta: SourceMeta = {
        gep: "idle",
        lcu: "idle",
        ocr: "idle",
        active: "手動入力",
      };
      const activeSources: string[] = [];

      try {
        const response = await fetchWithTimeout(`${API}/game/state`, {}, 4000);
        if (!response.ok) throw new Error(`game/state: ${response.status}`);
        const data = await response.json();

        if (data.in_game && data.state) {
          state = mergeAnalyzeState(state, {
            ...data.state,
            preferred_comp_id: stored.compId ?? null,
          });
          nextSourceMeta.gep = "ok";
          activeSources.push("GEP");
        } else {
          nextSourceMeta.gep = "miss";
        }
      } catch {
        nextSourceMeta.gep = "error";
      }

      if (nextSourceMeta.gep !== "ok") {
        try {
          const response = await fetchWithTimeout(`${API}/lcu/game`, {}, 4000);
          if (!response.ok) throw new Error(`lcu/game: ${response.status}`);
          const data = await response.json();

          if (data.in_game && data.state) {
            state = mergeAnalyzeState(state, {
              ...data.state,
              preferred_comp_id: stored.compId ?? null,
            });
            nextSourceMeta.lcu = "ok";
            activeSources.push("LCU");
          } else {
            nextSourceMeta.lcu = "miss";
          }
        } catch {
          nextSourceMeta.lcu = "error";
        }
      }

      const hasLiveState = nextSourceMeta.gep === "ok" || nextSourceMeta.lcu === "ok";
      const useFastCapture = hasLiveState || inGameRef.current;

      try {
        const response = await fetchWithTimeout(`${API}/capture`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ include_preview: false, existing_state: state, fast: useFastCapture }),
        }, useFastCapture ? 18000 : 7000);
        if (!response.ok) throw new Error(`capture: ${response.status}`);
        const data = await response.json();

        if (data.state) {
          state = mergeAnalyzeState(state, {
            ...data.state,
            preferred_comp_id: stored.compId ?? null,
          });
          nextSourceMeta.ocr = "ok";
          activeSources.push("OCR");
        } else {
          nextSourceMeta.ocr = "miss";
        }
      } catch {
        nextSourceMeta.ocr = "error";
      }

      if (stored.compId) {
        state = {
          ...state,
          preferred_comp_id: stored.compId,
        };
      }

      applyOverlayState(state);
      lastStateRef.current = state;
      setSourceMeta({
        ...nextSourceMeta,
        active: activeSources.length > 0 ? activeSources.join(" + ") : "手動入力",
      });

      const response = await fetchWithTimeout(`${API}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state),
      }, 8000);
      if (!response.ok) throw new Error(`analyze: ${response.status}`);

      const analyzed = (await response.json()) as AnalyzeResponse;
      setResult(analyzed);
      resultRef.current = analyzed;
      writeOverlayLiveSnapshot({
        updatedAt: Date.now(),
        inGame: true,
        state,
        result: analyzed,
      });

      if (analyzed.topComp?.id) {
        writeOverlayContext({
          compId: analyzed.topComp.id,
          stage: state.stage,
          hp: state.hp,
          items: state.items,
        });
      }

      setLastTs(new Date().toLocaleTimeString());
    } catch (error) {
      setErrMsg(error instanceof Error ? error.message : "解析に失敗しました");
    } finally {
      busyRef.current = false;
      setBusy(false);
      if (queuedAnalyzeRef.current && autoRef.current && inGameRef.current) {
        queuedAnalyzeRef.current = false;
        window.setTimeout(() => {
          void analyze();
        }, 150);
      }
    }
  }, [applyOverlayState, gold, hp, level, stage]);

  const scheduleAnalyze = useCallback((delay = 450) => {
    if (!autoRef.current || !inGameRef.current) return;

    if (analyzeTimerRef.current !== null) {
      window.clearTimeout(analyzeTimerRef.current);
    }

    analyzeTimerRef.current = window.setTimeout(() => {
      analyzeTimerRef.current = null;
      void analyze();
    }, delay);
  }, [analyze]);

  const handleDebugSave = useCallback(async () => {
    setDebugSaving(true);
    try {
      const response = await fetchWithTimeout(`${API}/capture/screenshot`, { method: "POST" }, 5000);
      if (!response.ok) throw new Error(`capture/screenshot: ${response.status}`);

      const data = await response.json();
      const capture: DebugCapture = {
        summary: (data.summary ?? {}) as Record<string, unknown>,
        low_confidence: (data.low_confidence ?? {}) as Record<string, number>,
        png: String(data.png ?? data.file ?? ""),
        timestamp: String(data.timestamp ?? ""),
        label: String(data.label ?? "manual"),
      };

      setDebugResult(capture);
      setLastCaptureTs(capture.timestamp || new Date().toLocaleTimeString());
    } catch (error) {
      setErrMsg(error instanceof Error ? error.message : "キャプチャ保存に失敗しました");
    } finally {
      setDebugSaving(false);
    }
  }, []);

  const loadAutoSaveStatus = useCallback(async () => {
    try {
      const response = await fetchWithTimeout(`${API}/capture/auto-save/status`, {}, 3000);
      if (!response.ok) throw new Error(`auto-save/status: ${response.status}`);
      const data = (await response.json()) as AutoSaveStatus;
      setAutoSaveStatus(data);
    } catch {
      // Screenshot collection is auxiliary; ignore transient failures.
    }
  }, []);

  const updateAutoSaveConfig = useCallback(async (patch: AutoSaveConfigPatch) => {
    setAutoSaveBusy(true);
    try {
      const response = await fetch(`${API}/capture/auto-save/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!response.ok) throw new Error(`auto-save/config: ${response.status}`);
      const data = (await response.json()) as AutoSaveStatus;
      setAutoSaveStatus(data);
    } catch (error) {
      setErrMsg(error instanceof Error ? error.message : "自動スクショ設定の更新に失敗しました");
    } finally {
      setAutoSaveBusy(false);
    }
  }, []);

  const toggleAutoSave = useCallback(() => {
    void updateAutoSaveConfig({ enabled: !(autoSaveStatus?.enabled ?? false) });
  }, [autoSaveStatus, updateAutoSaveConfig]);

  const cycleAutoSaveInterval = useCallback(() => {
    const options = [5, 10, 15, 30];
    const current = autoSaveStatus?.interval_sec ?? 15;
    const index = options.indexOf(current);
    const next = options[(index + 1 + options.length) % options.length];
    void updateAutoSaveConfig({ interval_sec: next });
  }, [autoSaveStatus, updateAutoSaveConfig]);

  useEffect(() => {
    checkGame();
    const id = window.setInterval(checkGame, 3000);
    return () => window.clearInterval(id);
  }, [checkGame]);

  useEffect(() => {
    void loadAutoSaveStatus();
    const id = window.setInterval(() => {
      void loadAutoSaveStatus();
    }, 5000);
    return () => window.clearInterval(id);
  }, [loadAutoSaveStatus]);

  useEffect(() => {
    const eventSource = new EventSource(`${API}/gep/stream`);

    eventSource.onmessage = (event) => {
      if (!event.data) return;

      try {
        const payload = JSON.parse(event.data) as GepStreamPayload;
        const live = Boolean(payload.in_game);

        setInGame(live);
        if (!live) {
          resultRef.current = null;
          clearOverlayLiveSnapshot();
        }
        setSourceMeta((current) => ({
          ...current,
          gep: live ? "ok" : current.gep === "error" ? "error" : "miss",
        }));

        if (!live || !payload.state) {
          lastGepSignatureRef.current = "";
          return;
        }

        const nextState = mergeAnalyzeState(lastStateRef.current, payload.state);

        applyOverlayState(nextState);

        const signature = JSON.stringify({
          revision: payload.revision ?? 0,
          stage: nextState.stage,
          level: nextState.level,
          hp: nextState.hp,
          gold: nextState.gold,
          board: nextState.board.map((unit) => `${unit.name}:${unit.stars}`),
          bench: nextState.bench.map((unit) => `${unit.name}:${unit.stars}`),
          shop: nextState.shop.map((unit) => `${unit.name}:${unit.stars}`),
          items: nextState.items,
          augments: nextState.augments,
        });

        if (signature !== lastGepSignatureRef.current) {
          lastGepSignatureRef.current = signature;
          scheduleAnalyze();
        }
      } catch {
        setSourceMeta((current) => ({ ...current, gep: "error" }));
      }
    };

    eventSource.onerror = () => {
      setSourceMeta((current) => ({
        ...current,
        gep: current.gep === "ok" ? "ok" : "error",
      }));
    };

    return () => {
      eventSource.close();
    };
  }, [applyOverlayState, scheduleAnalyze]);

  useEffect(() => {
    const eventSource = new EventSource(`${API}/game/screen-state`);

    eventSource.onmessage = (event) => {
      if (!event.data) return;

      try {
        const payload = JSON.parse(event.data) as ScreenStatePayload;
        const isSelection = payload.state === "selection" || Boolean(payload.selection_type);

        if (!isSelection) {
          lastSelectionSignatureRef.current = "";
          clearSelectionContext();
          hideSelectionPopups(false);
          return;
        }

        const popupStage = normalizeStage(
          payload.stage ?? readOverlayContext().stage ?? stage,
          stage || DEFAULT_ANALYZE_REQUEST.stage,
        );
        const augments = Array.isArray(payload.augments) ? payload.augments.filter(Boolean) : [];
        const gods = Array.isArray(payload.gods) ? payload.gods.filter(Boolean) : [];
        const forgeItems = Array.isArray(payload.forge_items) ? payload.forge_items.filter(Boolean) : [];
        const boons = Array.isArray(payload.boons) ? payload.boons.filter(Boolean) : [];

        let popupPage: PopupPage = "augment";
        if (payload.selection_type === "god") popupPage = "gods";
        if (payload.selection_type === "forge") popupPage = "forge";
        if (payload.selection_type === "godboon") popupPage = "godboon";
        if (
          popupStage === "4-7" &&
          popupPage === "augment" &&
          augments.length === 0 &&
          gods.length === 0 &&
          forgeItems.length === 0
        ) {
          popupPage = "godboon";
        }

        const popupChoices =
          popupPage === "gods" ? gods :
          popupPage === "forge" ? forgeItems :
          popupPage === "godboon" ? boons :
          augments;

        const popupAllowed = isSelectionPopupAllowed(popupPage, popupStage, {
          augments: augments.length,
          gods: gods.length,
          forgeItems: forgeItems.length,
          boons: boons.length,
        });

        if (!popupAllowed) {
          clearSelectionContext();
          hideSelectionPopups(false);
          return;
        }

        if (popupChoices.length === 0 && popupPage !== "godboon") {
          return;
        }

        writeSelectionContext({
          type:
            popupPage === "gods" ? "god" :
            popupPage === "forge" ? "forge" :
            popupPage === "godboon" ? "godboon" :
            "augment",
          stage: popupStage,
          augments,
          gods,
          forgeItems,
          boons,
          updatedAt: Date.now(),
        });

        const signature = JSON.stringify({
          popupPage,
          popupStage,
          popupChoices,
        });

        if (signature === lastSelectionSignatureRef.current && activeSelectionPopupRef.current === popupPage) {
          return;
        }

        lastSelectionSignatureRef.current = signature;
        if (autoRef.current) {
          showPopup(popupPage, popupStage, "auto");
        }
      } catch {
        // Ignore transient OCR/SSE parse failures for selection detection.
      }
    };

    return () => {
      eventSource.close();
    };
  }, [hideSelectionPopups, showPopup, stage]);

  useEffect(() => {
    if ((autoMode && inGame) || analyzeTimerRef.current === null) return;
    window.clearTimeout(analyzeTimerRef.current);
    analyzeTimerRef.current = null;
  }, [autoMode, inGame]);

  useEffect(() => {
    if (!autoMode || !inGame) return;

    void analyze();
    const id = window.setInterval(() => {
      if (autoRef.current && inGameRef.current) {
        void analyze();
      }
    }, 5000);

    return () => window.clearInterval(id);
  }, [analyze, autoMode, inGame]);

  const handleHeaderMouseDown = useCallback((event: React.MouseEvent) => {
    const target = event.target instanceof HTMLElement ? event.target : null;
    if (target?.closest("button, input, select, textarea, a")) {
      return;
    }

    if (bridge) {
      bridge.dragStart();
      const onMove = () => bridge.dragMove();
      const onUp = () => {
        bridge.dragEnd();
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      event.preventDefault();
      return;
    }

    const node = rootRef.current;
    if (!node) return;

    const rect = node.getBoundingClientRect();
    const startLeft = rect.left;
    const startTop = rect.top;
    const startX = event.clientX;
    const startY = event.clientY;

    node.style.left = `${startLeft}px`;
    node.style.top = `${startTop}px`;
    node.style.right = "auto";
    node.style.bottom = "auto";

    const onMove = (moveEvent: MouseEvent) => {
      if (!rootRef.current) return;
      rootRef.current.style.left = `${startLeft + moveEvent.clientX - startX}px`;
      rootRef.current.style.top = `${startTop + moveEvent.clientY - startY}px`;
    };
    const onUp = () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    event.preventDefault();
  }, []);

  const openPopup = useCallback((page: PopupPage) => {
    const popupStage = stage || DEFAULT_ANALYZE_REQUEST.stage;
    showPopup(page, popupStage, "manual");
  }, [showPopup, stage]);

  const situations = result?.situationActions ?? [];
  const orderedSituations = [
    ...situations.filter((item) => item.priority === "urgent"),
    ...situations.filter((item) => item.priority === "high"),
    ...situations.filter((item) => item.priority === "medium"),
  ];
  const visibleSituations = detailsOpen ? orderedSituations.slice(0, 5) : orderedSituations.slice(0, 3);
  const visibleShop = detailsOpen
    ? (result?.shopRecommendations ?? [])
    : (result?.shopRecommendations.slice(0, 3) ?? []);
  const shopHighlights = buildShopHighlights(lastStateRef.current.shop, result?.shopRecommendations ?? []);
  const visibleBoardAdvice = detailsOpen ? (result?.boardAdvice ?? []) : [];
  const visibleCutCandidates = detailsOpen ? (result?.cutCandidates ?? []) : [];
  const visibleNextImprovements = detailsOpen ? (result?.nextImprovements ?? []) : [];
  const autoSaveLastTs = autoSaveStatus?.last_saved_at
    ? new Date(autoSaveStatus.last_saved_at * 1000).toLocaleTimeString()
    : "";
  const autoSaveHint =
    autoSaveStatus?.last_saved_path ||
    autoSaveStatus?.last_skip_reason ||
    autoSaveStatus?.last_screen_state ||
    "waiting";

  return (
    <div
      ref={rootRef}
      className="overlay-root v2-root v2-topbar-root"
      onMouseEnter={() => bridge?.mouseEnter()}
      onMouseLeave={() => bridge?.mouseLeave()}
    >
      <div className="v2-topbar" onMouseDown={handleHeaderMouseDown}>
        <span className={`v2-dot ${inGame ? "v2-dot-green" : "v2-dot-gray"}`} />

        <span className="v2-stat-chip" onMouseDown={(event) => event.stopPropagation()}>
          <span className="v2-stat-value">{stage}</span>
        </span>

        {inGame && <span className="v2-topbar-meta">Lv {level}</span>}
        {inGame && (
          <span className="v2-topbar-hp" style={hp <= 40 ? { color: "#f87171" } : undefined}>
            HP {hp}
          </span>
        )}
        {inGame && <span className="v2-topbar-meta">G {gold}</span>}
        {busy && <span className="v2-spin">...</span>}

        <div className="v2-topbar-actions" onMouseDown={(event) => event.stopPropagation()}>
          <button className="v2-topbar-btn v2-topbar-btn-primary" onClick={analyze} disabled={busy}>
            Analyze
          </button>
          <button
            className={`v2-topbar-btn ${autoMode ? "v2-topbar-btn-auto-on" : "v2-topbar-btn-auto-off"}`}
            onClick={() => setAutoMode((value) => !value)}
            disabled={busy}
          >
            {autoMode ? "Auto" : "Manual"}
          </button>
          <button className="v2-topbar-btn v2-topbar-btn-cam" onClick={handleDebugSave} disabled={debugSaving}>
            {debugSaving ? "..." : "Cap"}
          </button>
          {/*
          <button
            className={`v2-topbar-btn ${autoSaveStatus?.enabled ? "v2-topbar-btn-shot-on" : "v2-topbar-btn-shot-off"}`}
            onClick={toggleAutoSave}
            disabled={autoSaveBusy}
            title="screenshots/data に定期保存"
          >
            {autoSaveStatus?.enabled ? "Shot ON" : "Shot OFF"}
          </button>
          <button
            className="v2-topbar-btn v2-topbar-btn-shot-int"
            onClick={cycleAutoSaveInterval}
            disabled={autoSaveBusy}
            title="自動スクショ間隔"
          >
            {autoSaveStatus?.interval_sec ?? 15}s
          </button>
          */}
          <button
            className={`v2-topbar-btn ${autoSaveStatus?.enabled ? "v2-topbar-btn-shot-on" : "v2-topbar-btn-shot-off"}`}
            onClick={toggleAutoSave}
            disabled={autoSaveBusy}
            title={autoSaveStatus?.output_dir ? `Auto save to ${autoSaveStatus.output_dir}` : "Auto save screenshots"}
          >
            {autoSaveStatus?.enabled ? "Shot ON" : "Shot OFF"}
          </button>
          <button
            className="v2-topbar-btn v2-topbar-btn-shot-int"
            onClick={cycleAutoSaveInterval}
            disabled={autoSaveBusy}
            title="Auto screenshot interval"
          >
            {autoSaveStatus?.interval_sec ?? 15}s
          </button>
          <button className="v2-topbar-btn v2-topbar-btn-aug" onClick={() => openPopup("augment")}>
            Aug
          </button>
          <button className="v2-topbar-btn v2-topbar-btn-god" onClick={() => openPopup("gods")}>
            GOD
          </button>
          <button className="v2-topbar-btn v2-topbar-btn-forge" onClick={() => openPopup("forge")}>
            Forge
          </button>
          <button className="v2-topbar-btn v2-topbar-btn-forge" onClick={() => openPopup("godboon")}>
            Boon
          </button>
        </div>

        <div className="v2-topbar-end" onMouseDown={(event) => event.stopPropagation()}>
          <button
            className="v2-topbar-icon-btn"
            onClick={() => setDetailsOpen((value) => !value)}
            title={detailsOpen ? "詳細を閉じる" : "詳細を開く"}
          >
            {detailsOpen ? "簡" : "詳"}
          </button>
          <button
            className="v2-topbar-icon-btn"
            onClick={() => setMinimized((value) => !value)}
            title={minimized ? "展開" : "折りたたみ"}
          >
            {minimized ? "+" : "-"}
          </button>
          {bridge && (
            <button className="v2-topbar-icon-btn v2-topbar-close" onClick={() => bridge.close()} title="閉じる">
              x
            </button>
          )}
        </div>
      </div>

      {!minimized && (
        <div className={detailsOpen ? "v2-topbar-panel v2-topbar-panel-expanded" : "v2-topbar-panel"}>
          <div className="v2-source-row">
            <span className={sourceChipClass(sourceMeta.gep)}>GEP {SOURCE_LABEL[sourceMeta.gep]}</span>
            <span className={sourceChipClass(sourceMeta.lcu)}>LCU {SOURCE_LABEL[sourceMeta.lcu]}</span>
            <span className={sourceChipClass(sourceMeta.ocr)}>OCR {SOURCE_LABEL[sourceMeta.ocr]}</span>
            <span className="v2-source-active">{sourceMeta.active}</span>
          </div>

          {errMsg && <p className="v2-err">{errMsg}</p>}

          {!result ? (
            <p className="v2-empty">{inGame ? "解析中..." : "TFT を起動すると自動で解析します"}</p>
          ) : (
            <>
              {visibleSituations.length > 0 && (
                <div className="v2-section">
                  <div className="v2-sec-hdr">今やること</div>
                  {visibleSituations.map((item, index) => (
                    <div
                      key={`${item.action}-${index}`}
                      className="v2-situation-item"
                      style={{ borderLeftColor: PRIORITY_COLOR[item.priority] }}
                    >
                      <div className="v2-sit-action" style={{ color: PRIORITY_COLOR[item.priority] }}>
                        {item.priority === "urgent" ? "[Urgent] " : ""}
                        {item.action}
                      </div>
                      {detailsOpen && item.detail && <div className="v2-sit-detail">{item.detail}</div>}
                    </div>
                  ))}
                </div>
              )}

              <div className="v2-section">
                <div className="v2-sec-hdr">狙う構成</div>
                <div className="v2-comp-row">
                  {result.topComp.tier && (
                    <span
                      className={`tier-badge tier-${result.topComp.tier}`}
                      style={{ width: 20, height: 20, fontSize: 10, borderRadius: 4 }}
                    >
                      {result.topComp.tier}
                    </span>
                  )}
                  <span className="v2-comp-name">{result.topComp.name}</span>
                  <span className="v2-comp-score">{result.boardStrength}</span>
                </div>
                {result.topComp.carry && <div className="v2-comp-carry">Carry: {result.topComp.carry}</div>}
                <div className="v2-comp-stats">
                  <span>W {(result.topComp.win_rate * 100).toFixed(0)}%</span>
                  <span>TOP4 {(result.topComp.top4_rate * 100).toFixed(0)}%</span>
                  <span>Avg {result.topComp.avg_placement.toFixed(1)}</span>
                </div>
              </div>

              <div className="v2-section v2-economy-section">
                <div className="v2-sec-hdr">レベル/リロール</div>
                <div className="v2-economy-action">{result.economyPlan.action}</div>
                {detailsOpen && result.economyPlan.reason && (
                  <div className="v2-economy-reason">{result.economyPlan.reason}</div>
                )}
              </div>

              {(shopHighlights.length > 0 || visibleShop.length > 0) && (
                <div className="v2-section">
                  <div className="v2-sec-hdr">Shop</div>
                  {shopHighlights.length > 0 && (
                    <div className="ov-shop-slots">
                      {shopHighlights.map((item) => (
                        <div
                          key={`${item.unit.name}-${item.slot}`}
                          className={`ov-shop-slot ${
                            item.action === "buy"
                              ? "ov-shop-slot-buy"
                              : item.action === "skip"
                                ? "ov-shop-slot-skip"
                                : "ov-shop-slot-maybe"
                          }`}
                        >
                          <div className="ov-shop-slot-top">
                            <span className="ov-shop-slot-index">{item.slot + 1}</span>
                            <span className="ov-shop-slot-badge">{shopActionLabel(item.action)}</span>
                          </div>
                          <div className="ov-shop-slot-name">{item.unit.name}</div>
                          <div className="ov-shop-slot-meta">
                            <span className="ov-shop-slot-stars">{"★".repeat(item.unit.stars)}</span>
                            {item.score > 0 && <span className="ov-shop-slot-score">{item.score}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {visibleShop.length > 0 && (
                    <ul className="ov-shop-list">
                      {visibleShop.map((item, index) => (
                        <li
                          key={`${item.name}-${index}`}
                          className={`ov-shop-item ${
                            item.action === "buy"
                              ? "ov-shop-buy"
                              : item.action === "skip"
                                ? "ov-shop-skip"
                                : "ov-shop-maybe"
                          }`}
                        >
                          <div className="ov-shop-line">
                            {item.action === "buy" && <span className="ov-buy-dot" />}
                            <span className="ov-shop-name">{item.name}</span>
                            <span className="ov-shop-action">{shopActionLabel(item.action)}</span>
                          </div>
                          {detailsOpen && item.reason && <div className="ov-shop-reason">{item.reason}</div>}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {result.itemPlan && (
                <div className="v2-section">
                  <div className="v2-sec-hdr">作るアイテム</div>
                  <div className="v2-item-plan">{result.itemPlan}</div>
                </div>
              )}

              {visibleBoardAdvice.length > 0 && (
                <div className="v2-section">
                  <div className="v2-sec-hdr">集める/置く</div>
                  {visibleBoardAdvice.map((item, index) => (
                    <div
                      key={`${item.label}-${index}`}
                      className={`v2-advice-item ${item.priority === "high" ? "v2-adv-high" : "v2-adv-mid"}`}
                    >
                      <span className="v2-adv-badge">{item.priority === "high" ? "High" : "Mid"}</span>
                      <span className="v2-adv-text">{item.label}</span>
                      <span className="v2-adv-reason">{item.reason}</span>
                    </div>
                  ))}
                </div>
              )}

              {visibleCutCandidates.length > 0 && (
                <div className="v2-section">
                  <div className="v2-sec-hdr">外す候補</div>
                  {visibleCutCandidates.map((item, index) => (
                    <div key={`${item.name}-${index}`} className="v2-cut-item">
                      - {item.name}
                      {item.reason && <span className="v2-cut-reason"> / {item.reason}</span>}
                    </div>
                  ))}
                </div>
              )}

              {visibleNextImprovements.length > 0 && (
                <div className="v2-section">
                  <div className="v2-sec-hdr">次の候補</div>
                  <ul className="v2-next-list">
                    {visibleNextImprovements.map((item, index) => (
                      <li key={`${item}-${index}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {debugResult && (
            <div className="ov-debug-panel">
              <div className="ov-debug-header">
                <span>Capture</span>
                <span className="ov-debug-path" title={debugResult.png}>
                  {debugResult.label} / {debugResult.png}
                </span>
                <button className="ov-debug-close" onClick={() => setDebugResult(null)}>
                  x
                </button>
              </div>
              <div className="ov-debug-stats">
                {["stage", "level", "hp", "gold"].map((key) => (
                  <span key={key} className="ov-debug-stat">
                    {key}: {String(debugResult.summary[key] ?? "-")}
                  </span>
                ))}
              </div>
              {(["board", "bench", "shop", "items", "augments"] as const).map((section) => {
                const values = (debugResult.summary[section] as string[] | undefined) ?? [];
                if (values.length === 0) return null;
                return (
                  <div key={section} className="ov-debug-units">
                    <span className="ov-debug-section">{section}</span>
                    {values.map((name, index) => (
                      <span key={`${section}-${name}-${index}`} className="ov-debug-unit">
                        {name}
                      </span>
                    ))}
                  </div>
                );
              })}
              {Object.keys(debugResult.low_confidence).length > 0 && (
                <div className="ov-debug-warn">
                  Low confidence:{" "}
                  {Object.entries(debugResult.low_confidence)
                    .map(([key, value]) => `${key}(${Math.round(value * 100)}%)`)
                    .join(" / ")}
                </div>
              )}
            </div>
          )}

          <div className="ov-ts">
            {lastTs && <span>更新: {lastTs}</span>}
            {lastCaptureTs && <span className="ov-ts-save">Cap: {lastCaptureTs}</span>}
            {autoSaveStatus?.enabled && (
              <span className="ov-ts-save" title={autoSaveHint}>
                Shot: {autoSaveLastTs || `wait/${autoSaveStatus.interval_sec}s`}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
