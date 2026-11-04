const DEFAULT_API_BASE = "http://127.0.0.1:8010";

// A URL query parameter must never redirect screenshots or game state to an external host.
function localApiBase(candidate: string | null | undefined): string | null {
  if (!candidate) return null;
  try {
    const value = new URL(candidate);
    const isLoopback = ["127.0.0.1", "localhost", "[::1]"].includes(value.hostname);
    if (
      value.protocol !== "http:" ||
      !isLoopback ||
      value.username ||
      value.password ||
      value.pathname !== "/" ||
      value.search ||
      value.hash
    ) return null;
    return value.origin;
  } catch {
    return null;
  }
}

function readQueryOverride(param: string): string | null {
  try {
    return localApiBase(new URLSearchParams(window.location.search).get(param));
  } catch {
    return null;
  }
}

export const API_BASE = (() => {
  const runtimeConfig = (window as { __TFT_ADVISOR_CONFIG__?: { apiBase?: string } }).__TFT_ADVISOR_CONFIG__;
  const queryOverride = readQueryOverride("apiBase");

  if (queryOverride) return queryOverride;
  const configured = localApiBase(runtimeConfig?.apiBase) ||
    localApiBase(import.meta.env.VITE_API_BASE);
  if (configured) return configured;
  const pageOrigin = localApiBase(window.location.origin);
  if (pageOrigin && new URL(pageOrigin).port === "8010") return pageOrigin;
  return DEFAULT_API_BASE;
})();
