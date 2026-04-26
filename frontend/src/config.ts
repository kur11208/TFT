const DEFAULT_API_BASE = "http://localhost:8000";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function readQueryOverride(param: string): string | null {
  try {
    const value = new URLSearchParams(window.location.search).get(param);
    return value ? trimTrailingSlash(value) : null;
  } catch {
    return null;
  }
}

export const API_BASE = (() => {
  const runtimeConfig = (window as { __TFT_ADVISOR_CONFIG__?: { apiBase?: string } }).__TFT_ADVISOR_CONFIG__;
  const queryOverride = readQueryOverride("apiBase");

  if (queryOverride) return queryOverride;
  if (runtimeConfig?.apiBase) return trimTrailingSlash(runtimeConfig.apiBase);
  if (import.meta.env.VITE_API_BASE) return trimTrailingSlash(import.meta.env.VITE_API_BASE);

  if (window.location.origin.includes(":8000")) {
    return trimTrailingSlash(window.location.origin);
  }

  return DEFAULT_API_BASE;
})();
