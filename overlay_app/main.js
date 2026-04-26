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

const WIN_W = 640;
const WIN_H = 680;
const DIST_ENTRY = path.resolve(__dirname, "..", "frontend", "dist", "index.html");
const FRONTEND_CANDIDATES = [
  process.env.TFT_ADVISOR_FRONTEND_URL,
  "http://localhost:5173",
  "http://localhost:8000",
].filter(Boolean);
const WINDOW_LAYOUTS = {
  overlay: { width: WIN_W, height: WIN_H, anchor: "top-right", marginRight: 20, top: 60 },
  augment: { width: 380, height: 460, anchor: "bottom-left", left: 24, marginBottom: 120 },
  forge: { width: 360, height: 480, anchor: "top-left", left: 24, top: 96 },
  gods: { width: 400, height: 520, anchor: "bottom-left", left: 24, marginBottom: 120 },
  godboon: { width: 380, height: 460, anchor: "bottom-left", left: 24, marginBottom: 120 },
};

let frontendBase = "http://localhost:8000";
let win = null;
let augWin = null;
let forgeWin = null;
let godsWin = null;
let boonWin = null;

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

  return "http://localhost:8000";
}

function buildAppUrl(params = {}) {
  if (frontendBase.startsWith("file:")) {
    const url = new URL(frontendBase);
    Object.entries(params).forEach(([key, value]) => {
      if (value) url.searchParams.set(key, String(value));
    });
    return url.toString();
  }

  const url = new URL(`${frontendBase}/`);
  Object.entries(params).forEach(([key, value]) => {
    if (value) url.searchParams.set(key, String(value));
  });
  return url.toString();
}

function resolveWindowBounds(layout) {
  const { width: screenWidth, height: screenHeight } = screen.getPrimaryDisplay().workAreaSize;
  const width = layout.width;
  const height = layout.height;

  if (layout.anchor === "top-right") {
    return {
      width,
      height,
      x: screenWidth - width - (layout.marginRight ?? 20),
      y: layout.top ?? 60,
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
  browserWindow.setContentProtection(true);
  browserWindow.setAlwaysOnTop(true, "screen-saver", 1);
  browserWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  return browserWindow;
}

function createWindow() {
  const bounds = resolveWindowBounds(WINDOW_LAYOUTS.overlay);

  win = new BrowserWindow({
    ...bounds,
    transparent: true,
    frame: false,
    backgroundColor: "#00000000",
    hasShadow: false,
    skipTaskbar: true,
    resizable: true,
    alwaysOnTop: true,
    focusable: true,
    fullscreenable: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.setContentProtection(true);
  win.setAlwaysOnTop(true, "screen-saver", 1);
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  win.setIgnoreMouseEvents(true, { forward: true });
  win.loadURL(buildAppUrl({ overlay: "2" }));
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
ipcMain.on("mouse-leave", () => {
  if (!dragging) {
    win?.setIgnoreMouseEvents(true, { forward: true });
  }
});
ipcMain.on("close-overlay", () => win?.hide());
ipcMain.on("minimize", () => win?.minimize());

ipcMain.on("drag-start", () => {
  if (!win) return;
  dragging = true;
  dragStartCursor = screen.getCursorScreenPoint();
  dragStartWinPos = win.getPosition();
  win.setIgnoreMouseEvents(false);
});

ipcMain.on("drag-move", () => {
  if (!dragging || !win || !dragStartCursor || !dragStartWinPos) return;
  const cursor = screen.getCursorScreenPoint();
  const deltaX = cursor.x - dragStartCursor.x;
  const deltaY = cursor.y - dragStartCursor.y;
  win.setPosition(dragStartWinPos[0] + deltaX, dragStartWinPos[1] + deltaY);
});

ipcMain.on("drag-end", () => {
  dragging = false;
  dragStartCursor = null;
  dragStartWinPos = null;
  win?.setIgnoreMouseEvents(true, { forward: true });
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
      win.hide();
      return;
    }
    win.show();
    win.setAlwaysOnTop(true, "screen-saver", 1);
  });

  globalShortcut.register("Alt+R", () => {
    if (!win) return;
    const bounds = resolveWindowBounds(WINDOW_LAYOUTS.overlay);
    win.setBounds(bounds);
    win.show();
    win.setAlwaysOnTop(true, "screen-saver", 1);
  });
}

app.whenReady().then(async () => {
  frontendBase = await resolveFrontendBase();
  createWindow();
  createPopupWindows();
  registerHotkeys();

  setInterval(() => {
    [win, augWin, forgeWin, godsWin, boonWin].forEach((browserWindow) => {
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
