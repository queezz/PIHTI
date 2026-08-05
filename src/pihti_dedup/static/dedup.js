(function () {
  "use strict";

  var host = document.getElementById("dup-results");
  if (!host) return;

  var FILTER_KEY = "pihti-dedup-filter";
  var FILTER_KINDS = { all: true, collision: true, exact: true, renamed: true };
  var filterState = readFilterState();
  var toastTimer = null;

  function readFilterState() {
    var fallback = {
      query: "", kind: "all", system: "", merge: "", extension: "",
      cross: false, includeVendor: false,
    };
    try {
      var saved = JSON.parse(localStorage.getItem(FILTER_KEY) || "{}");
      Object.keys(fallback).forEach(function (key) {
        if (typeof saved[key] === typeof fallback[key]) fallback[key] = saved[key];
      });
    } catch (_) { /* storage disabled or stale — keep in-memory defaults */ }
    if (!FILTER_KINDS[filterStateKind(fallback.kind)]) fallback.kind = "all";
    return fallback;
  }

  function filterStateKind(value) {
    return String(value || "").toLowerCase();
  }

  function saveFilterState() {
    try { localStorage.setItem(FILTER_KEY, JSON.stringify(filterState)); }
    catch (_) { /* state still survives fragment swaps in memory */ }
  }

  function showToast(message) {
    var old = document.querySelector("[data-operation-toast]");
    if (old) old.remove();
    if (toastTimer) window.clearTimeout(toastTimer);
    var toast = document.createElement("div");
    toast.className = "operation-toast";
    toast.dataset.operationToast = "true";
    toast.setAttribute("role", "status");
    toast.textContent = message;
    document.body.appendChild(toast);
    toastTimer = window.setTimeout(function () { toast.remove(); }, 8000);
  }

  function captureViewportAnchor(removingCard) {
    var visible = Array.from(host.querySelectorAll("[data-group]")).filter(function (card) {
      return !card.hidden;
    });
    var anchor = null;
    if (removingCard) {
      var index = visible.indexOf(removingCard);
      anchor = visible[index + 1] || visible[index - 1] || null;
    }
    if (!anchor) {
      anchor = visible.find(function (card) {
        return card.getBoundingClientRect().bottom > 64;
      }) || null;
    }
    return {
      id: anchor ? anchor.id : "",
      top: anchor ? anchor.getBoundingClientRect().top : 0,
      scrollY: window.scrollY || document.documentElement.scrollTop || 0,
      focusNext: Boolean(removingCard),
    };
  }

  function restoreViewportAnchor(anchor) {
    if (!anchor) return;
    window.requestAnimationFrame(function () {
      var card = anchor.id ? document.getElementById(anchor.id) : null;
      if (card && !card.hidden) {
        window.scrollBy(0, card.getBoundingClientRect().top - anchor.top);
        if (anchor.focusNext) {
          var action = card.querySelector("[data-member-delete], [data-copy]");
          if (action) action.focus({ preventScroll: true });
        }
        return;
      }
      var maximum = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      window.scrollTo(0, Math.min(anchor.scrollY, maximum));
    });
  }

  function loadingMarkup() {
    return '<div class="loading-card" role="status"><span class="spinner" aria-hidden="true"></span>' +
      '<div><strong>Reading the workspace</strong><small>Hashing CAD files and grouping filenames…</small></div></div>';
  }

  async function loadResults(options) {
    options = options || {};
    var includeVendor = options.includeVendor;
    if (typeof includeVendor === "undefined") {
      includeVendor = filterState.includeVendor;
    }
    filterState.includeVendor = Boolean(includeVendor);
    saveFilterState();
    host.dataset.includeVendor = includeVendor ? "true" : "false";
    if (options.preserveView) {
      host.classList.add("is-refreshing");
      host.setAttribute("aria-busy", "true");
    } else {
      host.innerHTML = loadingMarkup();
    }

    var url = new URL(host.dataset.src, window.location.origin);
    if (includeVendor) url.searchParams.set("include_vendor", "1");
    if (options.refresh) url.searchParams.set("refresh", "1");
    try {
      var response = await fetch(url.toString(), { headers: { "X-Requested-With": "fetch" } });
      var body = await response.text();
      host.innerHTML = body;
      host.classList.remove("is-refreshing");
      host.removeAttribute("aria-busy");
      if (!response.ok) throw new Error("Scan request failed (" + response.status + ")");
      bindResults(options.anchor || null);
      if (options.notice) showToast(options.notice);
    } catch (error) {
      host.classList.remove("is-refreshing");
      host.removeAttribute("aria-busy");
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

  function bindResults(viewAnchor) {
    var cards = Array.from(host.querySelectorAll("[data-group]"));
    var search = host.querySelector("[data-filter-search]");
    var extension = host.querySelector("[data-filter-extension]");
    var cross = host.querySelector("[data-filter-cross]");
    var count = host.querySelector("[data-visible-count]");
    var empty = host.querySelector("[data-no-results]");
    var vendor = host.querySelector("[data-include-vendor]");
    var cleanupCard = host.querySelector("[data-cleanup-card]");
    var cleanupNote = host.querySelector("[data-cleanup-note]");
    var planButton = host.querySelector("[data-plan-run]");
    var applyButton = host.querySelector("[data-cleanup-apply]");
    var referencesChecked = host.querySelector("[data-references-checked]");
    var planPanel = host.querySelector("[data-plan-panel]");
    var planTitle = host.querySelector("[data-plan-title]");
    var planSummary = host.querySelector("[data-plan-summary]");
    var planList = host.querySelector("[data-plan-list]");
    var activeKind = FILTER_KINDS[filterState.kind] ? filterState.kind : "all";
    var activeSystem = filterState.system;
    var activeMerge = filterState.merge;
    var selectedMerge = null;
    var currentPlan = null;

    function applyFilters() {
      var needle = search.value.trim().toLowerCase();
      var selectedExtension = extension.value;
      var visible = 0;
      cards.forEach(function (card) {
        var kindsMatch = activeKind === "all" || card.dataset.kind === activeKind;
        var textMatch = !needle || card.dataset.search.indexOf(needle) !== -1;
        var systems = card.dataset.systems.split("|");
        var systemMatch = !activeSystem || systems.indexOf(activeSystem) !== -1;
        var merges = card.dataset.merges.split("|");
        var mergeMatch = !activeMerge || merges.indexOf(activeMerge) !== -1;
        var extensions = card.dataset.extensions.split("|");
        var extensionMatch = !selectedExtension || extensions.indexOf(selectedExtension) !== -1;
        var crossMatch = !cross.checked || card.dataset.cross === "true";
        var shown = kindsMatch && textMatch && systemMatch && mergeMatch && extensionMatch && crossMatch;
        card.hidden = !shown;
        if (shown) visible += 1;
      });
      count.textContent = String(visible);
      empty.hidden = visible !== 0;
    }

    search.value = filterState.query;
    if (Array.from(extension.options).some(function (option) {
      return option.value === filterState.extension;
    })) extension.value = filterState.extension;
    else filterState.extension = "";
    cross.checked = filterState.cross;

    search.addEventListener("input", function () {
      filterState.query = search.value;
      saveFilterState();
      applyFilters();
    });
    extension.addEventListener("change", function () {
      filterState.extension = extension.value;
      saveFilterState();
      applyFilters();
    });
    cross.addEventListener("change", function () {
      filterState.cross = cross.checked;
      saveFilterState();
      applyFilters();
    });

    function selectButton(buttons, selected) {
      buttons.forEach(function (candidate) {
        var current = candidate === selected;
        candidate.classList.toggle("is-active", current);
        candidate.setAttribute("aria-pressed", current ? "true" : "false");
      });
    }

    function formatBytes(value) {
      var units = ["B", "KB", "MB", "GB"];
      var size = Number(value);
      var unit = 0;
      while (size >= 1024 && unit < units.length - 1) {
        size /= 1024;
        unit += 1;
      }
      return (unit === 0 ? String(size) : size.toFixed(1)) + " " + units[unit];
    }

    function windowsPath(value) {
      return value.replaceAll("/", "\\");
    }

    function formatModified(value) {
      return new Date(Number(value) / 1000000).toLocaleString();
    }

    function resetCleanupContext(button) {
      selectedMerge = button && button.dataset.planSrc ? button : null;
      currentPlan = null;
      planPanel.hidden = true;
      referencesChecked.checked = false;
      referencesChecked.disabled = true;
      planButton.disabled = !selectedMerge;
      applyButton.disabled = true;
      if (!selectedMerge) {
        cleanupNote.textContent = "Select one merged PR.";
        return;
      }
      cleanupNote.textContent = selectedMerge.dataset.cleanupCandidates +
        " merge-added exact copies are eligible for preview.";
    }

    function renderPlan(plan) {
      planTitle.textContent = "PR #" + plan.pr_number + " exact-copy cleanup";
      planSummary.textContent = plan.summary.candidates + " files · " +
        formatBytes(plan.summary.candidate_bytes) + " would move to recoverable quarantine. " +
        plan.summary.protected_groups + " all-merge groups stay protected.";
      planList.replaceChildren();
      if (!plan.candidates.length) {
        var emptyItem = document.createElement("li");
        var emptyCode = document.createElement("code");
        emptyCode.textContent = "Nothing would be moved.";
        emptyItem.appendChild(emptyCode);
        planList.appendChild(emptyItem);
      }
      plan.candidates.forEach(function (candidate) {
        var item = document.createElement("li");
        var path = document.createElement("code");
        var size = document.createElement("span");
        var keeps = document.createElement("small");
        path.textContent = "WOULD QUARANTINE " + windowsPath(candidate.path);
        size.textContent = formatBytes(candidate.size) + " · modified " +
          formatModified(candidate.mtime_ns);
        keeps.textContent = "KEEP " + candidate.keep_paths.map(windowsPath).join(" · KEEP ");
        item.append(path, size, keeps);
        planList.appendChild(item);
      });
      planPanel.hidden = false;
      referencesChecked.disabled = !plan.candidates.length;
      applyButton.disabled = true;
      planPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    var kindButtons = host.querySelectorAll("[data-kind-filter]");
    var restoredKind = Array.from(kindButtons).find(function (button) {
      return button.dataset.kindFilter === activeKind;
    }) || kindButtons[0];
    activeKind = restoredKind ? restoredKind.dataset.kindFilter : "all";
    filterState.kind = activeKind;
    selectButton(kindButtons, restoredKind);
    kindButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        activeKind = button.dataset.kindFilter;
        filterState.kind = activeKind;
        saveFilterState();
        selectButton(kindButtons, button);
        applyFilters();
      });
    });
    var folderButtons = host.querySelectorAll("[data-system-filter]");
    var restoredFolder = Array.from(folderButtons).find(function (button) {
      return button.dataset.systemFilter === activeSystem;
    }) || folderButtons[0];
    activeSystem = restoredFolder ? restoredFolder.dataset.systemFilter : "";
    filterState.system = activeSystem;
    selectButton(folderButtons, restoredFolder);
    folderButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        activeSystem = button.dataset.systemFilter;
        filterState.system = activeSystem;
        saveFilterState();
        selectButton(folderButtons, button);
        applyFilters();
      });
    });
    var mergeButtons = host.querySelectorAll("[data-merge-filter]");
    var restoredMerge = Array.from(mergeButtons).find(function (button) {
      return button.dataset.mergeFilter === activeMerge;
    }) || mergeButtons[0];
    activeMerge = restoredMerge ? restoredMerge.dataset.mergeFilter : "";
    filterState.merge = activeMerge;
    selectButton(mergeButtons, restoredMerge);
    mergeButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        activeMerge = button.dataset.mergeFilter;
        filterState.merge = activeMerge;
        saveFilterState();
        selectButton(mergeButtons, button);
        resetCleanupContext(button);
        applyFilters();
      });
    });

    planButton.addEventListener("click", async function () {
      if (!selectedMerge) return;
      planButton.disabled = true;
      planButton.textContent = "Planning…";
      var url = new URL(selectedMerge.dataset.planSrc, window.location.origin);
      if (vendor.checked) url.searchParams.set("include_vendor", "1");
      try {
        var response = await fetch(url.toString(), { headers: { "X-Requested-With": "fetch" } });
        var plan = await response.json();
        if (!response.ok) throw new Error(plan.error || "Dry run failed");
        currentPlan = plan;
        renderPlan(plan);
      } catch (error) {
        cleanupNote.textContent = error.message;
      } finally {
        planButton.disabled = false;
        planButton.textContent = "Preview --dry";
      }
    });
    referencesChecked.addEventListener("change", function () {
      applyButton.disabled = !currentPlan || !currentPlan.candidates.length ||
        !referencesChecked.checked;
    });
    host.querySelector("[data-plan-close]").addEventListener("click", function () {
      planPanel.hidden = true;
    });
    applyButton.addEventListener("click", async function () {
      if (!selectedMerge || !currentPlan || !referencesChecked.checked) return;
      var count = currentPlan.summary.candidates;
      if (!window.confirm(
        "Move " + count + " merge-added exact copies to recoverable quarantine?"
      )) return;
      applyButton.disabled = true;
      applyButton.textContent = "Revalidating…";
      try {
        var response = await fetch(selectedMerge.dataset.applySrc, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-PIHTI-Token": cleanupCard.dataset.formToken,
          },
          body: JSON.stringify({
            signature: currentPlan.signature,
            references_checked: true,
            include_vendor: vendor.checked,
          }),
        });
        var result = await response.json();
        if (!response.ok) throw new Error(result.error || "Cleanup failed");
        var moved = result.execution.moved.length;
        var manifest = result.execution.manifest ?
          windowsPath(result.execution.manifest) : "no manifest needed";
        loadResults({
          includeVendor: vendor.checked,
          notice: "Quarantined " + moved + " files. Restoration manifest: " + manifest,
          preserveView: true,
          anchor: captureViewportAnchor(),
        });
      } catch (error) {
        cleanupNote.textContent = error.message;
        applyButton.disabled = false;
        applyButton.textContent = "Apply to quarantine";
      }
    });
    vendor.addEventListener("change", function () {
      filterState.includeVendor = vendor.checked;
      saveFilterState();
      loadResults({
        includeVendor: vendor.checked,
        preserveView: true,
        anchor: captureViewportAnchor(),
      });
    });
    host.querySelectorAll("[data-refresh]").forEach(function (button) {
      button.addEventListener("click", function () {
        loadResults({
          includeVendor: vendor.checked,
          refresh: true,
          preserveView: true,
          anchor: captureViewportAnchor(),
        });
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
    host.querySelectorAll("[data-member-delete]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var displayPath = button.dataset.displayPath;
        var keepPath = button.dataset.keep;
        var viewAnchor = captureViewportAnchor(button.closest("[data-group]"));
        if (!window.confirm(
          "Delete this file from the Inventor workspace?\n\n" + displayPath +
          "\n\nIt will move to recoverable quarantine. Byte-identical survivor:\n" +
          keepPath + "\n\nContinue only after checking Inventor references."
        )) return;
        button.disabled = true;
        button.textContent = "Deleting…";
        try {
          var response = await fetch(button.dataset.deleteSrc, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-PIHTI-Token": cleanupCard.dataset.formToken,
            },
            body: JSON.stringify({
              path: button.dataset.path,
              signature: button.dataset.signature,
              references_checked: true,
              include_vendor: vendor.checked,
            }),
          });
          var result = await response.json();
          if (!response.ok) throw new Error(result.error || "Delete failed");
          loadResults({
            includeVendor: vendor.checked,
            notice: "Deleted to recoverable quarantine: " + displayPath +
              ". Restoration manifest: " + windowsPath(result.execution.manifest),
            preserveView: true,
            anchor: viewAnchor,
          });
        } catch (error) {
          window.alert(error.message);
          button.disabled = false;
          button.textContent = "Delete";
        }
      });
    });
    resetCleanupContext(restoredMerge && restoredMerge.dataset.planSrc ? restoredMerge : null);
    applyFilters();
    saveFilterState();
    restoreViewportAnchor(viewAnchor);
  }

  loadResults({ includeVendor: filterState.includeVendor });
})();

(function () {
  "use strict";

  var search = document.querySelector("[data-catalog-search]");
  if (!search) return;

  var tiles = Array.from(document.querySelectorAll("[data-catalog-item]"));
  var folders = Array.from(document.querySelectorAll("[data-catalog-folder]"));
  var counter = document.querySelector("[data-catalog-count]");
  var empty = document.querySelector("[data-catalog-empty]");

  function filterCatalog() {
    var query = search.value.trim().toLowerCase();
    var shown = 0;
    tiles.forEach(function (tile) {
      var match = !query || tile.dataset.search.indexOf(query) !== -1;
      tile.hidden = !match;
      if (match) shown += 1;
    });
    folders.forEach(function (folder) {
      folder.hidden = !folder.querySelector("[data-catalog-item]:not([hidden])");
    });
    if (counter) counter.textContent = String(shown);
    if (empty) empty.hidden = shown !== 0;
  }

  search.addEventListener("input", filterCatalog);
  filterCatalog();
})();
