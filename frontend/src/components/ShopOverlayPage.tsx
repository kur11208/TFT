import React, { useEffect, useMemo, useState } from "react";

import { API_BASE as API } from "../config";
import { buildShopHighlights, shopActionLabel } from "../utils/shopHighlights";
import { OVERLAY_LIVE_KEY, readOverlayLiveSnapshot } from "../utils/overlayLive";

type ShopOverlayRect = {
  slot: number;
  x: number;
  y: number;
  w: number;
  h: number;
};

type ShopOverlayLayoutResponse = {
  screen_width: number;
  screen_height: number;
  slots: ShopOverlayRect[];
};

type ShopOverlayLayout = {
  screenWidth: number;
  screenHeight: number;
  slots: ShopOverlayRect[];
};

type ViewportSize = {
  width: number;
  height: number;
};

function getViewportSize(): ViewportSize {
  return {
    width: window.visualViewport?.width || window.innerWidth || document.documentElement.clientWidth || 0,
    height: window.visualViewport?.height || window.innerHeight || document.documentElement.clientHeight || 0,
  };
}

function scaleRectToViewport(
  rect: ShopOverlayRect,
  layout: ShopOverlayLayout,
  viewport: ViewportSize,
): ShopOverlayRect {
  const scaleX = layout.screenWidth > 0 && viewport.width > 0 ? viewport.width / layout.screenWidth : 1;
  const scaleY = layout.screenHeight > 0 && viewport.height > 0 ? viewport.height / layout.screenHeight : 1;
  return {
    slot: rect.slot,
    x: Math.round(rect.x * scaleX),
    y: Math.round(rect.y * scaleY),
    w: Math.round(rect.w * scaleX),
    h: Math.round(rect.h * scaleY),
  };
}

export function ShopOverlayPage() {
  const [snapshot, setSnapshot] = useState(() => readOverlayLiveSnapshot());
  const [layout, setLayout] = useState<ShopOverlayLayout>({
    screenWidth: 0,
    screenHeight: 0,
    slots: [],
  });
  const [viewport, setViewport] = useState(() => getViewportSize());

  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    const root = document.getElementById("root");

    html.classList.add("shop-overlay-page");
    body.classList.add("shop-overlay-page");
    if (root) root.classList.add("shop-overlay-page");

    return () => {
      html.classList.remove("shop-overlay-page");
      body.classList.remove("shop-overlay-page");
      if (root) root.classList.remove("shop-overlay-page");
    };
  }, []);

  useEffect(() => {
    const updateViewport = () => setViewport(getViewportSize());

    updateViewport();
    window.addEventListener("resize", updateViewport);
    window.visualViewport?.addEventListener("resize", updateViewport);

    return () => {
      window.removeEventListener("resize", updateViewport);
      window.visualViewport?.removeEventListener("resize", updateViewport);
    };
  }, []);

  useEffect(() => {
    let active = true;

    const loadLayout = async () => {
      try {
        const response = await fetch(`${API}/capture/shop-overlay-layout`, { cache: "no-store" });
        if (!response.ok) return;
        const data = (await response.json()) as ShopOverlayLayoutResponse;
        if (!active) return;
        setLayout({
          screenWidth: Number(data.screen_width) || 0,
          screenHeight: Number(data.screen_height) || 0,
          slots: Array.isArray(data.slots) ? data.slots : [],
        });
      } catch {
        if (!active) return;
        setLayout({ screenWidth: 0, screenHeight: 0, slots: [] });
      }
    };

    void loadLayout();
    window.addEventListener("resize", loadLayout);
    return () => {
      active = false;
      window.removeEventListener("resize", loadLayout);
    };
  }, []);

  useEffect(() => {
    const sync = () => setSnapshot(readOverlayLiveSnapshot());
    sync();

    const timer = window.setInterval(sync, 300);
    const onStorage = (event: StorageEvent) => {
      if (event.key && event.key !== OVERLAY_LIVE_KEY) return;
      sync();
    };

    window.addEventListener("storage", onStorage);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const highlights = useMemo(() => {
    const ageMs = Date.now() - snapshot.updatedAt;
    if (!snapshot.inGame || ageMs > 10000) return [];

    const bySlot = new Map(
      layout.slots.map((item) => [item.slot, scaleRectToViewport(item, layout, viewport)]),
    );
    return buildShopHighlights(snapshot.state.shop, snapshot.result?.shopRecommendations ?? [])
      .filter((item) => item.action !== "skip")
      .map((item) => {
        const rect = bySlot.get(item.slot + 1);
        if (!rect) return null;
        return { ...item, rect };
      })
      .filter((item): item is NonNullable<typeof item> => item !== null);
  }, [layout, snapshot, viewport]);

  return (
    <div className="shop-overlay-root">
      {highlights.map((item) => (
        <div
          key={`${item.unit.name}-${item.slot}`}
          className={`shop-overlay-card ${
            item.action === "buy" ? "shop-overlay-buy" : "shop-overlay-maybe"
          }`}
          style={{
            left: item.rect.x,
            top: item.rect.y,
            width: item.rect.w,
            height: item.rect.h,
          }}
        >
          <div className="shop-overlay-head">
            <span className="shop-overlay-slot">{item.slot + 1}</span>
            <span className="shop-overlay-badge">{shopActionLabel(item.action)}</span>
          </div>
          <div className="shop-overlay-name">{item.unit.name}</div>
          {item.reason && <div className="shop-overlay-reason">{item.reason}</div>}
        </div>
      ))}
    </div>
  );
}
