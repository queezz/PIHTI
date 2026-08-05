(function () {
  "use strict";

  var host = document.getElementById("dup-results");
  if (!host) return;

  function loadingMarkup() {
    return '<div class="loading-card" role="status"><span class="spinner" aria-hidden="true"></span>' +
      '<div><strong>Reading the workspace</strong><small>Hashing CAD files and grouping filenames…</small></div></div>';
  }

  async function loadResults(options) {
    options = options || {};
    var includeVendor = options.includeVendor;
    if (typeof includeVendor === "undefined") {
      includeVendor = host.dataset.includeVendor === "true";
    }
    host.dataset.includeVendor = includeVendor ? "true" : "false";
    host.innerHTML = loadingMarkup();

    var url = new URL(host.dataset.src, window.location.origin);
    if (includeVendor) url.searchParams.set("include_vendor", "1");
    if (options.refresh) url.searchParams.set("refresh", "1");
    try {
      var response = await fetch(url.toString(), { headers: { "X-Requested-With": "fetch" } });
      var body = await response.text();
      host.innerHTML = body;
      if (!response.ok) throw new Error("Scan request failed (" + response.status + ")");
      bindResults();
    } catch (error) {
      if (!host.querySelector(".error-card")) {
        host.innerHTML = '<section class="error-card" role="alert"><p class="eyebrow">Scan stopped</p>' +
          '<h2>The workspace could not be inventoried.</h2><p>' + escapeHtml(error.message) + '</p>' +
          '<button class="button" type="button" data-refresh>Try again</button></section>';
      }
      bindRetry();
    }
  }

  function escapeHtml(value) {
    var node = document.createElement("div");
    node.textContent = value;
    return node.innerHTML;
  }

  function bindRetry() {
    var retry = host.querySelector("[data-refresh]");
    if (retry) retry.addEventListener("click", function () { loadResults({ refresh: true }); });
  }

  function bindResults() {
    var cards = Array.from(host.querySelectorAll("[data-group]"));
    var search = host.querySelector("[data-filter-search]");
    var system = host.querySelector("[data-filter-system]");
    var extension = host.querySelector("[data-filter-extension]");
    var cross = host.querySelector("[data-filter-cross]");
    var count = host.querySelector("[data-visible-count]");
    var empty = host.querySelector("[data-no-results]");
    var activeKind = "all";

    function applyFilters() {
      var needle = search.value.trim().toLowerCase();
      var selectedSystem = system.value;
      var selectedExtension = extension.value;
      var visible = 0;
      cards.forEach(function (card) {
        var kindsMatch = activeKind === "all" || card.dataset.kind === activeKind;
        var textMatch = !needle || card.dataset.search.indexOf(needle) !== -1;
        var systems = card.dataset.systems.split("|");
        var systemMatch = !selectedSystem || systems.indexOf(selectedSystem) !== -1;
        var extensions = card.dataset.extensions.split("|");
        var extensionMatch = !selectedExtension || extensions.indexOf(selectedExtension) !== -1;
        var crossMatch = !cross.checked || card.dataset.cross === "true";
        var shown = kindsMatch && textMatch && systemMatch && extensionMatch && crossMatch;
        card.hidden = !shown;
        if (shown) visible += 1;
      });
      count.textContent = String(visible);
      empty.hidden = visible !== 0;
    }

    [search, system, extension, cross].forEach(function (control) {
      control.addEventListener(control === search ? "input" : "change", applyFilters);
    });
    host.querySelectorAll("[data-kind]").forEach(function (button) {
      button.addEventListener("click", function () {
        activeKind = button.dataset.kind;
        host.querySelectorAll("[data-kind]").forEach(function (candidate) {
          var current = candidate === button;
          candidate.classList.toggle("is-active", current);
          candidate.setAttribute("aria-pressed", current ? "true" : "false");
        });
        applyFilters();
      });
    });

    var vendor = host.querySelector("[data-include-vendor]");
    vendor.addEventListener("change", function () {
      loadResults({ includeVendor: vendor.checked });
    });
    host.querySelectorAll("[data-refresh]").forEach(function (button) {
      button.addEventListener("click", function () {
        loadResults({ includeVendor: vendor.checked, refresh: true });
      });
    });
    host.querySelectorAll("[data-copy]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var original = button.textContent;
        try {
          await navigator.clipboard.writeText(button.dataset.copy);
          button.textContent = "Copied";
        } catch (_) {
          button.textContent = "Copy failed";
        }
        window.setTimeout(function () { button.textContent = original; }, 1200);
      });
    });
    applyFilters();
  }

  loadResults();
})();
