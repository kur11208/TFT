const {
  app,
  BrowserWindow,
  ipcMain,
  screen,
  globalShortcut,
} = require("electron");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const WIN_W = 440;
const WIN_H = 240;
const DIST_ENTRY = path.resolve(__dirname, "..", "frontend", "dist", "index.html");
const API_BASE_OVERRIDE = process.env.TFT_ADVISOR_API_BASE || "";
const FRONTEND_CANDIDATES = [
  process.env.TFT_ADVISOR_FRONTEND_URL,
  "http://127.0.0.1:5173",
  "http://[::1]:5173",
  "http://localhost:5173",
].filter(Boolean);
const BASE_SCREEN_WIDTH = 1920;
const WINDOW_LAYOUTS = {
  overlay: { width: WIN_W, height: WIN_H, anchor: "fixed", left: 369, top: 43 },
  augment: { width: 380, height: 460, anchor: "top-left", left: 24, top: 88, minWidth: 220, minHeight: 340, safeLeftEdge: 422 },
  forge: { width: 360, height: 480, anchor: "top-left", left: 24, top: 96, minWidth: 220, minHeight: 360, safeLeftEdge: 422 },
  gods: { width: 360, height: 500, anchor: "top-left", left: 24, top: 88, minWidth: 240, minHeight: 380, safeLeftEdge: 696 },
  godboon: { width: 380, height: 460, anchor: "top-left", left: 24, top: 88, minWidth: 220, minHeight: 340, safeLeftEdge: 422 },
};
const OVERLAY_MIN_WIDTH = 440;
const OVERLAY_MIN_HEIGHT = 64;
const OVERLAY_FIXED = true;

let frontendBase = "http://127.0.0.1:8010";
let win = null;
let shopWin = null;
let augWin = null;
let forgeWin = null;
let godsWin = null;
let boonWin = null;
let overlayMoved = false;

let dragging = false;
let dragStartCursor = null;
let dragStartWinPos = null;

async function probeHttp(base) {
  try {
    const response = await fetch(`${String(base).replace(/\/+$/, "")}/`, {
      method: "GET",
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function resolveFrontendBase() {
  for (const candidate of FRONTEND_CANDIDATES) {
    if (await probeHttp(candidate)) {
      return String(candidate).replace(/\/+$/, "");
    }
  }

  if (fs.existsSync(DIST_ENTRY)) {
    return pathToFileURL(DIST_ENTRY).toString();
  }

  if (await probeHttp("http://127.0.0.1:8010")) {
    return "http://127.0.0.1:8010";
  }

  if (await probeHttp("http://localhost:8010")) {
    return "http://localhost:8010";
  }

  return "http://127.0.0.1:8010";
}

function buildAppUrl(params = {}) {
  if (frontendBase.startsWith("file:")) {
    const url = new URL(frontendBase);
    if (API_BASE_OVERRIDE) {
      url.searchParams.set("apiBase", String(API_BASE_OVERRIDE));
    }
    Object.entries(params).forEach(([key, value]) => {
      if (value) url.searchParams.set(key, String(value));
    });
    return url.toString();
  }

  const url = new URL(`${frontendBase}/`);
  if (API_BASE_OVERRIDE) {
    url.searchParams.set("apiBase", String(API_BASE_OVERRIDE));
  }
  Object.entries(params).forEach(([key, value]) => {
    if (value) url.searchParams.set(key, String(value));
  });
  return url.toString();
}

function resolveLayoutSize(layout, screenWidth, screenHeight) {
  let width = layout.width;
  let height = layout.height;

  if (layout.anchor === "top-left" && typeof layout.safeLeftEdge === "number") {
    const left = layout.left ?? 24;
    const safeMaxWidth = Math.floor((layout.safeLeftEdge * screenWidth) / BASE_SCREEN_WIDTH) - left - 18;
    if (Number.isFinite(safeMaxWidth) && safeMaxWidth > 0) {
      width = Math.min(width, safeMaxWidth);
    }
  }

  if (layout.anchor === "top-left") {
    const left = layout.left ?? 24;
    width = Math.min(width, screenWidth - left - 12);
    height = Math.min(height, screenHeight - (layout.top ?? 80) - 24);
  }

  if (typeof layout.minWidth === "number") {
    width = Math.max(layout.minWidth, width);
  }
  if (typeof layout.minHeight === "number") {
    height = Math.max(layout.minHeight, height);
  }

  return { width, height };
}

function resolveWindowBounds(layout) {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize;
  const size = resolveLayoutSize(layout, screenWidth, screenHeight);
  const width = size.width;
  const height = size.height;

  if (layout.anchor === "top-right") {
    return {
      width,
      height,
      x: screenWidth - width - (layout.marginRight ?? 20),
      y: layout.top ?? 60,
    };
  }

  if (layout.anchor === "fixed") {
    return {
      width,
      height,
      x: layout.left ?? 0,
      y: layout.top ?? 0,
    };
  }

  if (layout.anchor === "top-left") {
    return {
      width,
      height,
      x: layout.left ?? 24,
      y: layout.top ?? 80,
    };
  }

  if (layout.anchor === "bottom-left") {
    return {
      width,
      height,
      x: layout.left ?? 24,
      y: Math.max(80, screenHeight - height - (layout.marginBottom ?? 80)),
    };
  }

  return {
    width,
    height,
    x: layout.left ?? 24,
    y: Math.max(layout.minTop ?? 80, Math.floor(screenHeight / 2) - Math.floor(height / 2)),
  };
}

function resolveFullscreenBounds() {
  const display = screen.getPrimaryDisplay();
  return {
    x: display.bounds.x,
    y: display.bounds.y,
    width: display.bounds.width,
    height: display.bounds.height,
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function resizeOverlayWindow(width, height) {
  if (!win) return;

  const display = screen.getDisplayMatching(win.getBounds());
  const workArea = display.workArea;
  const nextWidth = clamp(Math.ceil(width), Math.min(OVERLAY_MIN_WIDTH, workArea.width), workArea.width);
  const nextHeight = clamp(Math.ceil(height), Math.min(OVERLAY_MIN_HEIGHT, workArea.height), workArea.height);
  const currentBounds = win.getBounds();
  const nextBounds = {
    x: currentBounds.x,
    y: currentBounds.y,
    width: nextWidth,
    height: nextHeight,
  };

  if (OVERLAY_FIXED || !overlayMoved) {
    nextBounds.x = workArea.x + (WINDOW_LAYOUTS.overlay.left ?? 0);
    nextBounds.y = workArea.y + (WINDOW_LAYOUTS.overlay.top ?? 0);
  } else {
    nextBounds.x = clamp(currentBounds.x, workArea.x, workArea.x + workArea.width - nextWidth);
    nextBounds.y = clamp(currentBounds.y, workArea.y, workArea.y + workArea.height - nextHeight);
  }

  if (
    nextBounds.x !== currentBounds.x ||
    nextBounds.y !== currentBounds.y ||
    nextBounds.width !== currentBounds.width ||
    nextBounds.height !== currentBounds.height
  ) {
    win.setBounds(nextBounds);
  }
}

function makePopupWindow(layout) {
  const bounds = resolveWindowBounds(layout);
  const browserWindow = new BrowserWindow({
    ...bounds,
    transparent: true,
    frame: false,
    backgroundColor: "#00000000",
    hasShadow: false,
    skipTaskbar: true,
    resizable: false,
    alwaysOnTop: true,
    focusable: true,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  browserWindow.setContentProtection(false);
  browserWindow.setAlwaysOnTop(true, "screen-saver", 1);
  browserWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  return browserWindow;
}

function createShopOverlayWindow() {
  const bounds = resolveFullscreenBounds();
  shopWin = new BrowserWindow({
    ...bounds,
    transparent: true,
    frame: false,
    backgroundColor: "#00000000",
    hasShadow: false,
    skipTaskbar: true,
    resizable: true,
    alwaysOnTop: true,
    focusable: false,
    fullscreenable: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  shopWin.setContentProtection(false);
  shopWin.setAlwaysOnTop(true, "screen-saver", 1);
  shopWin.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  shopWin.setIgnoreMouseEvents(true, { forward: true });
  shopWin.loadURL(buildAppUrl({ page: "shop-overlay" }));
  shopWin.on("closed", () => {
    shopWin = null;
  });
}

function syncShopOverlayBounds() {
  if (!shopWin) return;
  shopWin.setBounds(resolveFullscreenBounds());
}

function showPrimaryOverlays() {
  if (win) {
    win.show();
    win.setAlwaysOnTop(true, "screen-saver", 1);
  }
  if (shopWin) {
    syncShopOverlayBounds();
    shopWin.showInactive();
    shopWin.setAlwaysOnTop(true, "screen-saver", 1);
  }
}

function hidePrimaryOverlays() {
  shopWin?.hide();
  win?.hide();
}

function createWindow() {
  const bounds = resolveWindowBounds(WINDOW_LAYOUTS.overlay);
  overlayMoved = false;

  win = new BrowserWindow({
    ...bounds,
    transparent: true,
    frame: false,
    backgroundColor: "#00000000",
    hasShadow: false,
    skipTaskbar: true,
    resizable: false,
    movable: false,
    alwaysOnTop: true,
    focusable: true,
    fullscreenable: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.setContentProtection(false);
  win.setAlwaysOnTop(true, "screen-saver", 1);
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.loadURL(buildAppUrl({ overlay: "2" }));
  win.on("show", () => {
    if (shopWin) {
      syncShopOverlayBounds();
      shopWin.showInactive();
    }
  });
  win.on("hide", () => {
    shopWin?.hide();
  });
  win.on("minimize", () => {
    shopWin?.hide();
  });
  win.on("closed", () => {
    win = null;
  });
}

function createPopupWindows() {
  augWin = makePopupWindow(WINDOW_LAYOUTS.augment);
  augWin.on("closed", () => {
    augWin = null;
  });

  forgeWin = makePopupWindow(WINDOW_LAYOUTS.forge);
  forgeWin.on("closed", () => {
    forgeWin = null;
  });

  godsWin = makePopupWindow(WINDOW_LAYOUTS.gods);
  godsWin.on("closed", () => {
    godsWin = null;
  });

  boonWin = makePopupWindow(WINDOW_LAYOUTS.godboon);
  boonWin.on("closed", () => {
    boonWin = null;
  });
}

ipcMain.on("mouse-enter", () => win?.setIgnoreMouseEvents(false));
ipcMain.on("mouse-leave", () => win?.setIgnoreMouseEvents(false));
ipcMain.on("close-overlay", () => hidePrimaryOverlays());
ipcMain.on("minimize", () => hidePrimaryOverlays());
ipcMain.on("set-overlay-size", (_, size) => {
  if (
    !size ||
    typeof size.width !== "number" ||
    typeof size.height !== "number" ||
    !Number.isFinite(size.width) ||
    !Number.isFinite(size.height)
  ) {
    return;
  }

  resizeOverlayWindow(size.width, size.height);
});

ipcMain.on("drag-start", () => {
  if (OVERLAY_FIXED) return;
  if (!win) return;
  overlayMoved = true;
  dragging = true;
  dragStartCursor = screen.getCursorScreenPoint();
  dragStartWinPos = win.getPosition();
  win.setIgnoreMouseEvents(false);
});

ipcMain.on("drag-move", () => {
  if (OVERLAY_FIXED) return;
  if (!dragging || !win || !dragStartCursor || !dragStartWinPos) return;
  const cursor = screen.getCursorScreenPoint();
  const deltaX = cursor.x - dragStartCursor.x;
  const deltaY = cursor.y - dragStartCursor.y;
  win.setPosition(dragStartWinPos[0] + deltaX, dragStartWinPos[1] + deltaY);
});

ipcMain.on("drag-end", () => {
  if (OVERLAY_FIXED) return;
  dragging = false;
  dragStartCursor = null;
  dragStartWinPos = null;
  win?.setIgnoreMouseEvents(false);
});

ipcMain.on("show-augment", (_, stage) => {
  if (!augWin) return;
  augWin.loadURL(buildAppUrl({ page: "augment", stage: stage || "2-1" }));
  augWin.show();
  augWin.setAlwaysOnTop(true, "screen-saver", 1);
});

ipcMain.on("hide-augment", () => augWin?.hide());

ipcMain.on("show-forge", () => {
  if (!forgeWin) return;
  forgeWin.loadURL(buildAppUrl({ page: "forge" }));
  forgeWin.show();
  forgeWin.setAlwaysOnTop(true, "screen-saver", 1);
});

ipcMain.on("hide-forge", () => forgeWin?.hide());

ipcMain.on("show-gods", (_, stage) => {
  if (!godsWin) return;
  godsWin.loadURL(buildAppUrl({ page: "gods", stage: stage || "2-1" }));
  godsWin.show();
  godsWin.setAlwaysOnTop(true, "screen-saver", 1);
});

ipcMain.on("hide-gods", () => godsWin?.hide());

ipcMain.on("show-god-boon", () => {
  if (!boonWin) return;
  boonWin.loadURL(buildAppUrl({ page: "godboon" }));
  boonWin.show();
  boonWin.setAlwaysOnTop(true, "screen-saver", 1);
});

ipcMain.on("hide-god-boon", () => boonWin?.hide());

function registerHotkeys() {
  globalShortcut.register("Alt+T", () => {
    if (!win) return;
    if (win.isVisible()) {
      hidePrimaryOverlays();
      return;
    }
    showPrimaryOverlays();
  });

  globalShortcut.register("Alt+R", () => {
    if (!win) return;
    overlayMoved = false;
    const bounds = resolveWindowBounds(WINDOW_LAYOUTS.overlay);
    win.setBounds(bounds);
    win.show();
    win.setAlwaysOnTop(true, "screen-saver", 1);
  });
}

app.whenReady().then(async () => {
  frontendBase = await resolveFrontendBase();
  createWindow();
  createShopOverlayWindow();
  createPopupWindows();
  registerHotkeys();
  screen.on("display-metrics-changed", () => {
    syncShopOverlayBounds();
  });

  setInterval(() => {
    [win, shopWin, augWin, forgeWin, godsWin, boonWin].forEach((browserWindow) => {
      if (browserWindow?.isVisible()) {
        browserWindow.setAlwaysOnTop(true, "screen-saver", 1);
      }
    });
  }, 3000);
});

app.on("will-quit", () => globalShortcut.unregisterAll());
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
