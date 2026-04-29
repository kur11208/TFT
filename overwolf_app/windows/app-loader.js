(function () {
  var config = window.__TFT_ADVISOR_CONFIG__ || {};
  var resolvedBase = null;

  function unique(values) {
    var seen = {};
    var output = [];
    values.forEach(function (value) {
      if (!value || seen[value]) return;
      seen[value] = true;
      output.push(value);
    });
    return output;
  }

  function trimTrailingSlash(value) {
    return String(value || "").replace(/\/+$/, "");
  }

  async function probe(base) {
    try {
      var response = await fetch(trimTrailingSlash(base) + "/", { method: "GET", cache: "no-store" });
      return response.ok;
    } catch {
      return false;
    }
  }

  async function resolveFrontendBase() {
    if (resolvedBase) return resolvedBase;

    var candidates = unique((config.frontendCandidates || []).map(trimTrailingSlash));
    for (var i = 0; i < candidates.length; i += 1) {
      if (await probe(candidates[i])) {
        resolvedBase = candidates[i];
        return resolvedBase;
      }
    }

    resolvedBase = trimTrailingSlash(config.backendBase || "http://127.0.0.1:8010");
    return resolvedBase;
  }

  function buildUrl(base, page, params) {
    var url = new URL(trimTrailingSlash(base) + "/");
    if (page === "overlay") {
      url.searchParams.set("overlay", "2");
    } else {
      url.searchParams.set("page", page);
    }

    Object.keys(params || {}).forEach(function (key) {
      var value = params[key];
      if (value) url.searchParams.set(key, value);
    });
    return url.toString();
  }

  async function setIframeSource(options) {
    var iframe = document.getElementById(options.iframeId || "app");
    if (!iframe) return;

    var params = Object.assign({}, options.params || {});
    if (options.stageStorageKey) {
      try {
        var storedStage = localStorage.getItem(options.stageStorageKey);
        if (storedStage) params.stage = storedStage;
      } catch {}
    }

    var base = await resolveFrontendBase();
    iframe.src = buildUrl(base, options.page, params);
  }

  function bindStageStorage(options) {
    window.addEventListener("storage", function (event) {
      if (!options.stageStorageKey) return;
      if (event.key !== options.stageStorageKey && event.key !== "tft_frontend_base") return;
      setIframeSource(options);
    });
  }

  window.TFTAdvisorLoader = {
    bind: function (options) {
      bindStageStorage(options);
      return setIframeSource(options);
    },
  };
})();
