'use strict';

const BACKEND = (window.__TFT_ADVISOR_CONFIG__ && window.__TFT_ADVISOR_CONFIG__.backendBase) || 'http://127.0.0.1:8010';

const REQUIRED_FEATURES = [
  'gep_internal', 'game_info', 'live_client_data',
  'me', 'match_info', 'roster', 'store', 'board', 'bench', 'carousel', 'augments'
];
const BASE_SCREEN_WIDTH = 1920;

const winIds = {};
let gepState = {};
let featureRetries = 0;

// ── Utility ──────────────────────────────────────────────────────────────────

function tryParseJson(val) {
  if (typeof val !== 'string') return val;
  try { return JSON.parse(val); } catch { return val; }
}

function pickFeaturePayload(feature, keys = []) {
  const parsed = tryParseJson(feature);
  if (parsed == null) return undefined;
  if (typeof parsed === 'object' && !Array.isArray(parsed)) {
    for (const key of keys) {
      if (parsed[key] !== undefined) return tryParseJson(parsed[key]);
    }
  }
  return parsed;
}

function postToBackend(payload) {
  fetch(`${BACKEND}/gep/update`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).catch(() => {});
}

const WINDOW_LAYOUTS = {
  overlay: { width: 560, height: 80, anchor: 'top-right', marginRight: 20, top: 60 },
  augment: { width: 380, height: 460, anchor: 'top-left', left: 24, top: 88, minWidth: 220, minHeight: 340, safeLeftEdge: 422 },
  forge: { width: 360, height: 480, anchor: 'top-left', left: 24, top: 96, minWidth: 220, minHeight: 360, safeLeftEdge: 422 },
  gods: { width: 360, height: 500, anchor: 'top-left', left: 24, top: 88, minWidth: 240, minHeight: 380, safeLeftEdge: 696 },
  godboon: { width: 380, height: 460, anchor: 'top-left', left: 24, top: 88, minWidth: 220, minHeight: 340, safeLeftEdge: 422 }
};

function resolveLayoutSize(layout, screenWidth, screenHeight) {
  let width = layout.width;
  let height = layout.height;

  if (layout.anchor === 'top-left' && typeof layout.safeLeftEdge === 'number') {
    const left = layout.left ?? 24;
    const safeMaxWidth = Math.floor((layout.safeLeftEdge * screenWidth) / BASE_SCREEN_WIDTH) - left - 18;
    if (Number.isFinite(safeMaxWidth) && safeMaxWidth > 0) {
      width = Math.min(width, safeMaxWidth);
    }
  }

  if (layout.anchor === 'top-left') {
    const left = layout.left ?? 24;
    width = Math.min(width, screenWidth - left - 12);
    height = Math.min(height, screenHeight - (layout.top ?? 80) - 24);
  }

  if (typeof layout.minWidth === 'number') {
    width = Math.max(layout.minWidth, width);
  }
  if (typeof layout.minHeight === 'number') {
    height = Math.max(layout.minHeight, height);
  }

  return { width, height };
}

function resolveWindowPosition(layout) {
  const screenWidth = window.screen?.availWidth || 1920;
  const screenHeight = window.screen?.availHeight || 1080;
  const size = resolveLayoutSize(layout, screenWidth, screenHeight);
  const width = size.width;
  const height = size.height;

  if (layout.anchor === 'top-right') {
    return {
      x: screenWidth - width - (layout.marginRight ?? 20),
      y: layout.top ?? 60,
      width,
      height
    };
  }

  if (layout.anchor === 'top-left') {
    return {
      x: layout.left ?? 24,
      y: layout.top ?? 80,
      width,
      height
    };
  }

  if (layout.anchor === 'bottom-left') {
    return {
      x: layout.left ?? 24,
      y: Math.max(80, screenHeight - height - (layout.marginBottom ?? 80)),
      width,
      height
    };
  }

  return {
    x: layout.left ?? 24,
    y: Math.max(layout.minTop ?? 80, Math.floor((screenHeight - height) / 2)),
    width,
    height
  };
}

function positionWindow(name, windowId) {
  const layout = WINDOW_LAYOUTS[name];
  if (!layout || !windowId || typeof overwolf.windows.changePosition !== 'function') return;
  const { x, y, width, height } = resolveWindowPosition(layout);

  if (typeof overwolf.windows.changeSize === 'function') {
    overwolf.windows.changeSize({ window_id: windowId, width, height }, () => {});
  }
  overwolf.windows.changePosition(windowId, x, y, () => {});
}

// ── Window helpers ────────────────────────────────────────────────────────────

function openWindow(name) {
  overwolf.windows.obtainDeclaredWindow(name, (res) => {
    if (res.status !== 'success') return;
    winIds[name] = res.window.id;
    positionWindow(name, res.window.id);
    overwolf.windows.restore(res.window.id, () => {
      positionWindow(name, res.window.id);
    });
  });
}

function closeWindow(name) {
  const id = winIds[name];
  if (id) {
    overwolf.windows.minimize(id, () => {});
  } else {
    overwolf.windows.obtainDeclaredWindow(name, (res) => {
      if (res.status === 'success') overwolf.windows.minimize(res.window.id, () => {});
    });
  }
}

function toggleOverlay() {
  const id = winIds['overlay'];
  if (!id) { openWindow('overlay'); return; }
  overwolf.windows.getWindowState(id, (res) => {
    if (res.status === 'success' && res.window_state_ex === 'minimized') {
      overwolf.windows.restore(id, () => {});
    } else {
      overwolf.windows.minimize(id, () => {});
    }
  });
}

// ── GEP callbacks ─────────────────────────────────────────────────────────────

function onInfoUpdate(info) {
  if (!info || !info.info) return;
  const updates = {};

  const me = info.info.me;
  if (me) {
    if (me.gold     !== undefined) updates.gold   = parseFloat(me.gold) || 0;
    if (me.health   !== undefined) updates.health = parseFloat(me.health) || 0;
    if (me.items    !== undefined) updates.items  = tryParseJson(me.items);
    if (me.inventoryItems !== undefined) updates.items = tryParseJson(me.inventoryItems);
    if (me.xp       !== undefined) {
      const xp = tryParseJson(me.xp);
      if (xp && xp.level != null) updates.level = parseInt(xp.level);
    }
  }

  const mi = info.info.match_info;
  if (mi) {
    if (mi.round_type !== undefined) {
      const rt = tryParseJson(mi.round_type);
      const round = rt && (rt.round ?? rt.stage ?? rt.value);
      if (round !== undefined) updates.stage = round;
    }
    if (mi.game_stage !== undefined) {
      const gameStage = tryParseJson(mi.game_stage);
      updates.game_stage = gameStage;
      if (updates.stage === undefined) updates.stage = gameStage;
    }
  }

  const shop = pickFeaturePayload(info.info.store, ['shop_pieces', 'shop']);
  if (shop !== undefined) updates.shop = shop;

  const board = pickFeaturePayload(info.info.board, ['board_pieces', 'board']);
  if (board !== undefined) updates.board = board;

  const bench = pickFeaturePayload(info.info.bench, ['bench_pieces', 'bench']);
  if (bench !== undefined) updates.bench = bench;

  if (info.info.augments !== undefined) updates.augments = tryParseJson(info.info.augments);

  if (Object.keys(updates).length === 0) return;
  Object.assign(gepState, updates);
  postToBackend(gepState);
}

function onNewEvent(eventList) {
  if (!eventList || !eventList.events) return;
  for (const ev of eventList.events) {
    switch (ev.name) {
      case 'match_start':
        gepState = {};
        postToBackend({ event: 'match_start' });
        openWindow('overlay');
        break;
      case 'match_end':
        postToBackend({ event: 'match_end' });
        break;
      case 'round_start':
        postToBackend({ event: 'round_start', ...gepState });
        break;
    }
  }
}

function setRequiredFeatures() {
  overwolf.games.events.setRequiredFeatures(REQUIRED_FEATURES, (result) => {
    if (result.status !== 'success') {
      featureRetries++;
      const delay = Math.min(2000 * featureRetries, 15000);
      setTimeout(setRequiredFeatures, delay);
    } else {
      featureRetries = 0;
    }
  });
}

// ── IPC from overlay/popup windows ───────────────────────────────────────────

overwolf.windows.onMessageReceived.addListener((msg) => {
  if (!msg || !msg.content) return;
  const { type } = msg.content;
  switch (type) {
    case 'show_augment':    openWindow('augment');   break;
    case 'hide_augment':    closeWindow('augment');  break;
    case 'show_forge':      openWindow('forge');     break;
    case 'hide_forge':      closeWindow('forge');    break;
    case 'show_gods':       openWindow('gods');      break;
    case 'hide_gods':       closeWindow('gods');     break;
    case 'show_godboon':    openWindow('godboon');   break;
    case 'hide_godboon':    closeWindow('godboon');  break;
    case 'minimize_overlay':closeWindow('overlay');  break;
  }
});

// ── Hotkey ────────────────────────────────────────────────────────────────────

overwolf.settings.hotkeys.onPressed.addListener((hotkey) => {
  if (hotkey.name === 'toggle_overlay') toggleOverlay();
});

// ── Game lifecycle ────────────────────────────────────────────────────────────

overwolf.games.events.onInfoUpdates2.addListener(onInfoUpdate);
overwolf.games.events.onNewEvents.addListener(onNewEvent);

overwolf.games.onGameLaunched.addListener((info) => {
  if (info && info.classId === 5426) {
    setTimeout(setRequiredFeatures, 3000);
    openWindow('overlay');
  }
});

overwolf.games.onGameClosed.addListener((info) => {
  if (info && info.gameInfo && info.gameInfo.classId === 5426) {
    gepState = {};
    postToBackend({ event: 'game_closed' });
  }
});

// ── Init ──────────────────────────────────────────────────────────────────────

overwolf.windows.obtainDeclaredWindow('background', (res) => {
  if (res.status === 'success') winIds['background'] = res.window.id;
});

overwolf.games.getRunningGameInfo((info) => {
  if (info && info.classId === 5426) {
    setTimeout(setRequiredFeatures, 1000);
    openWindow('overlay');
  }
});
