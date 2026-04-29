(function () {
  function readStorage(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  var backendBase = readStorage("tft_backend_base") || "http://127.0.0.1:8010";
  var frontendOverride = readStorage("tft_frontend_base");
  var candidates = frontendOverride
    ? [frontendOverride, "http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8010"]
    : ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8010"];

  window.__TFT_ADVISOR_CONFIG__ = {
    backendBase: backendBase.replace(/\/+$/, ""),
    frontendCandidates: candidates.map(function (value) {
      return value.replace(/\/+$/, "");
    }),
  };
})();
