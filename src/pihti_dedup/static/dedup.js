(function () {
  "use strict";

  var host = document.getElementById("dup-results");
  if (!host) return;

  var FILTER_KEY = "pihti-dedup-filter";
  var FILTER_KINDS = { all: true, collision: true, exact: true, renamed: true };
  var filterState = readFilterState();
  var toastTimer = null;
  var resultsRequest = 0;
  var resultsController = null;

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
    var requestId = ++resultsRequest;
    if (resultsController) resultsController.abort();
    resultsController = new AbortController();
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
      var response = await fetch(url.toString(), {
        headers: { "X-Requested-With": "fetch" },
        signal: resultsController.signal,
      });
      var body = await response.text();
      if (requestId !== resultsRequest) return;
      host.innerHTML = body;
      host.classList.remove("is-refreshing");
      host.removeAttribute("aria-busy");
      if (!response.ok) throw new Error("Scan request failed (" + response.status + ")");
      bindResults(options.anchor || null);
      if (options.notice) showToast(options.notice);
    } catch (error) {
      if (error.name === "AbortError" || requestId !== resultsRequest) return;
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
        var shown = card.dataset.operationPending !== "true" && kindsMatch && textMatch &&
          systemMatch && mergeMatch && extensionMatch && crossMatch;
        card.hidden = !shown;
        if (shown) visible += 1;
      });
      count.textContent = String(visible);
      empty.hidden = visible !== 0;
    }

    function liveCards() {
      return cards.filter(function (card) {
        return card.isConnected && card.dataset.operationPending !== "true";
      });
    }

    function syncRailCounts() {
      var available = liveCards();
      host.querySelectorAll("[data-kind-filter]").forEach(function (button) {
        var kind = button.dataset.kindFilter;
        var value = kind === "all" ? available.length : available.filter(function (card) {
          return card.dataset.kind === kind;
        }).length;
        var output = button.querySelector("strong");
        if (output) output.textContent = String(value);
      });
      host.querySelectorAll("[data-system-filter]").forEach(function (button) {
        var system = button.dataset.systemFilter;
        var value = system ? available.filter(function (card) {
          return card.dataset.systems.split("|").indexOf(system) !== -1;
        }).length : available.length;
        var output = button.querySelector("strong");
        if (output) output.textContent = String(value);
      });
      host.querySelectorAll("[data-merge-filter]").forEach(function (button) {
        var merge = button.dataset.mergeFilter;
        var value = merge ? available.filter(function (card) {
          return card.dataset.merges.split("|").indexOf(merge) !== -1;
        }).length : available.length;
        var output = button.querySelector("strong");
        if (output) output.textContent = String(value);
      });
    }

    function removeCard(card) {
      var index = cards.indexOf(card);
      if (index !== -1) cards.splice(index, 1);
      card.remove();
      syncRailCounts();
      applyFilters();
    }

    function updateCardAfterMemberRemoval(card, row) {
      row.remove();
      var members = Array.from(card.querySelectorAll(".member"));
      if (members.length < 2) {
        removeCard(card);
        return;
      }
      var hashes = new Set(members.map(function (member) {
        return member.dataset.recordHash;
      }).filter(Boolean));
      var fileCount = card.querySelector("[data-group-file-count]");
      var hashCount = card.querySelector("[data-group-hash-count]");
      if (fileCount) fileCount.textContent = members.length + " files";
      if (hashCount) {
        hashCount.textContent = hashes.size + " distinct " +
          (hashes.size === 1 ? "hash" : "hashes");
      }
      if ((card.dataset.kind === "collision" || card.dataset.kind === "exact") && hashes.size) {
        var kind = hashes.size === 1 ? "exact" : "collision";
        card.classList.toggle("kind-collision", kind === "collision");
        card.classList.toggle("kind-exact", kind === "exact");
        card.dataset.kind = kind;
        var icon = card.querySelector(".kind-icon");
        var label = card.querySelector(".kind-label");
        if (icon) icon.textContent = kind === "collision" ? "≠" : "=";
        if (label) label.textContent = kind === "collision" ? "different bytes" : "identical bytes";
      }
      card.querySelectorAll("[data-member-delete], [data-consolidate-keep]").forEach(function (action) {
        action.disabled = true;
        action.title = "Rescan before another cleanup action in this changed group";
      });
      syncRailCounts();
      applyFilters();
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
        var isCollision = button.dataset.groupKind === "collision";
        var card = button.closest("[data-group]");
        var row = button.closest(".member");
        var hideWholeCard = card.querySelectorAll(".member").length <= 2;
        if (!window.confirm(
          "Move only this file to recoverable quarantine?\n\n" + displayPath +
          "\n\nRemaining same-name file(s):\n" + keepPath +
          (isCollision
            ? "\n\nThese files have different bytes. Continue only because you reviewed this revision."
            : "\n\nContinue only after checking Inventor references.")
        )) return;
        if (hideWholeCard) {
          card.dataset.operationPending = "true";
          applyFilters();
        } else {
          row.hidden = true;
        }
        showToast("Moving to quarantine: " + displayPath);
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
              reviewed: isCollision,
              include_vendor: vendor.checked,
            }),
          });
          var result = await response.json();
          if (!response.ok) throw new Error(result.error || "Delete failed");
          if (hideWholeCard) removeCard(card);
          else updateCardAfterMemberRemoval(card, row);
          showToast((result.already_applied ? "Already quarantined: " : "Quarantined: ") +
            displayPath + ". Restoration manifest: " +
            windowsPath(result.execution.manifest) +
            (hideWholeCard ? "" : ". Rescan before another action in this changed group."));
        } catch (error) {
          window.alert(error.message);
          delete card.dataset.operationPending;
          row.hidden = false;
          applyFilters();
          button.disabled = false;
          button.textContent = button.dataset.idleLabel;
        }
      });
    });
    host.querySelectorAll("[data-consolidate-keep]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var card = button.closest("[data-group]");
        var count = card.querySelectorAll(".member").length - 1;
        var keepPath = button.dataset.displayPath;
        if (!window.confirm(
          "Keep this reviewed revision and move the other " + count +
          " same-name file(s) to recoverable quarantine?\n\nKEEP:\n" + keepPath +
          "\n\nThis records where the removed paths went. Continue only because you opened " +
          "and compared these different-byte revisions."
        )) return;
        card.dataset.operationPending = "true";
        applyFilters();
        showToast("Moving reviewed revisions to quarantine…");
        button.disabled = true;
        button.textContent = "Quarantining…";
        try {
          var response = await fetch(button.dataset.consolidateSrc, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-PIHTI-Token": cleanupCard.dataset.formToken,
            },
            body: JSON.stringify({
              keep_path: button.dataset.keepPath,
              reviewed: true,
              include_vendor: vendor.checked,
            }),
          });
          var result = await response.json();
          if (!response.ok) throw new Error(result.error || "Consolidation failed");
          removeCard(card);
          showToast((result.already_applied ? "Already completed. " : "") +
            "Quarantined " + result.execution.moved.length +
            " reviewed revisions. Answer recorded under Removed.");
        } catch (error) {
          window.alert(error.message);
          delete card.dataset.operationPending;
          applyFilters();
          button.disabled = false;
          button.textContent = "Keep only this";
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

  var dialogs = Array.from(document.querySelectorAll("dialog.note-dialog"));
  if (!dialogs.length) return;

  document.querySelectorAll("[data-dialog-open]").forEach(function (opener) {
    opener.addEventListener("click", function () {
      var dialog = document.getElementById(opener.dataset.dialogOpen);
      if (dialog && !dialog.open) dialog.showModal();
    });
  });

  document.querySelectorAll("[data-dialog-close]").forEach(function (closer) {
    closer.addEventListener("click", function () {
      var dialog = closer.closest("dialog");
      if (dialog) dialog.close();
    });
  });

  dialogs.forEach(function (dialog) {
    // Native dialogs already close on Escape. Clicking the dimmed backdrop is
    // the pointer equivalent; clicks inside the shell do not bubble as target.
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
    if (dialog.hasAttribute("data-auto-open")) dialog.showModal();
  });
})();

(function () {
  "use strict";

  var form = document.querySelector("[data-live-note-form]");
  if (!form) return;
  var input = form.querySelector("[data-live-note-input]");
  var preview = document.querySelector("[data-note-preview-body]");
  var status = form.querySelector("[data-live-note-status]");
  var timer = null;
  var sequence = 0;

  function renderLive() {
    var current = ++sequence;
    if (status) status.textContent = "Updating preview…";
    var body = new FormData();
    body.append("text", input.value);
    fetch("/markdown/preview", { method: "POST", body: body })
      .then(function (response) {
        if (!response.ok) throw new Error("Preview unavailable");
        return response.json();
      })
      .then(function (result) {
        if (current !== sequence) return;
        preview.innerHTML = result.html;
        if (status) status.textContent = "Preview is current.";
      })
      .catch(function () {
        if (current === sequence && status) {
          status.textContent = "Preview could not update; your text is still safe.";
        }
      });
  }

  input.addEventListener("input", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(renderLive, 250);
  });
})();

(function () {
  "use strict";

  var form = document.querySelector("[data-live-note-form]");
  if (!form) return;
  var input = form.querySelector("[data-live-note-input]");
  var preview = document.querySelector("[data-note-preview-body]");
  var status = form.querySelector("[data-live-note-status]");
  var timer = null;
  var sequence = 0;

  function renderLive() {
    var current = ++sequence;
    if (status) status.textContent = "Updating preview…";
    var body = new FormData();
    body.append("text", input.value);
    fetch("/markdown/preview", { method: "POST", body: body })
      .then(function (response) {
        if (!response.ok) throw new Error("Preview unavailable");
        return response.json();
      })
      .then(function (result) {
        if (current !== sequence) return;
        preview.innerHTML = result.html;
        if (status) status.textContent = "Preview is current.";
      })
      .catch(function () {
        if (current === sequence && status) {
          status.textContent = "Preview could not update; your text is still safe.";
        }
      });
  }

  input.addEventListener("input", function () {
    window.clearTimeout(timer);
    timer = window.setTimeout(renderLive, 250);
  });
})();

(function () {
  "use strict";

  // The server opens the current folder's ancestry. Other branches reveal only
  // when asked and reset on navigation, so the rail never grows into another
  // rendering of the entire catalog.
  var tree = document.querySelector("[data-folder-tree]");
  if (!tree) return;

  function setOpen(path, open) {
    var toggle = tree.querySelector('[data-tree-toggle="' + CSS.escape(path) + '"]');
    var children = tree.querySelector('[data-tree-children="' + CSS.escape(path) + '"]');
    if (!toggle || !children) return;
    children.hidden = !open;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.classList.toggle("is-open", open);
  }

  tree.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-tree-toggle]");
    if (!toggle) return;
    var path = toggle.dataset.treeToggle;
    var open = toggle.getAttribute("aria-expanded") !== "true";
    setOpen(path, open);
  });
})();

(function () {
  "use strict";

  // Copy-to-clipboard outside the duplicates fragment: the renames page pastes
  // these straight into Inventor's resolve-link dialog.
  document.querySelectorAll("[data-copy-text]").forEach(function (button) {
    button.addEventListener("click", async function () {
      var original = button.textContent;
      try {
        await navigator.clipboard.writeText(button.dataset.copyText);
        button.textContent = "Copied";
      } catch (_) {
        button.textContent = "Copy failed";
      }
      window.setTimeout(function () { button.textContent = original; }, 1200);
    });
  });
})();

(function () {
  "use strict";

  var ledger = document.querySelector("[data-removed-ledger]");
  if (!ledger) return;

  var batches = Array.from(ledger.querySelectorAll("[data-removed-batch]"));
  var buttons = Array.from(ledger.querySelectorAll("[data-removed-filter]"));
  var empty = ledger.querySelector("[data-removed-filter-empty]");
  var active = "all";

  function applyRemovedFilter() {
    var shown = 0;
    batches.forEach(function (batch) {
      var visible = active === "all" || batch.dataset.status === active;
      batch.hidden = !visible;
      if (visible) shown += 1;
    });
    buttons.forEach(function (button) {
      var selected = button.dataset.removedFilter === active;
      button.classList.toggle("is-active", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    });
    if (empty) empty.hidden = shown !== 0;
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      active = button.dataset.removedFilter;
      applyRemovedFilter();
    });
  });
  var expand = ledger.querySelector("[data-removed-expand]");
  var collapse = ledger.querySelector("[data-removed-collapse]");
  if (expand) expand.addEventListener("click", function () {
    batches.forEach(function (batch) { if (!batch.hidden) batch.open = true; });
  });
  if (collapse) collapse.addEventListener("click", function () {
    batches.forEach(function (batch) { batch.open = false; });
  });
  applyRemovedFilter();
})();

(function () {
  "use strict";

  var ledger = document.querySelector("[data-rename-ledger]");
  if (!ledger) return;

  var CHECK_KEY = "pihti-rename-referrers";
  var search = ledger.querySelector("[data-rename-search]");
  var cards = Array.from(ledger.querySelectorAll("[data-rename-entry]"));
  var counter = ledger.querySelector("[data-rename-count]");
  var empty = ledger.querySelector("[data-rename-empty]");

  function readChecks() {
    try {
      var saved = JSON.parse(localStorage.getItem(CHECK_KEY) || "{}");
      return saved && typeof saved === "object" ? saved : {};
    } catch (_) { return {}; }
  }

  var checks = readChecks();

  // Per-referrer ticks are a local worklist, not a claim about the archive, so
  // they stay in localStorage. Only "settled" reaches the Git-tracked ledger.
  ledger.querySelectorAll("[data-referrer-check]").forEach(function (box) {
    var key = box.dataset.referrerCheck;
    box.checked = Boolean(checks[key]);
    box.addEventListener("change", function () {
      if (box.checked) checks[key] = true;
      else delete checks[key];
      try { localStorage.setItem(CHECK_KEY, JSON.stringify(checks)); }
      catch (_) { /* the tick still holds for this visit */ }
    });
  });

  ledger.querySelectorAll("[data-rename-settled]").forEach(function (box) {
    var id = box.dataset.renameSettled;
    var status = ledger.querySelector('[data-rename-status="' + CSS.escape(id) + '"]');
    box.addEventListener("change", async function () {
      var wanted = box.checked;
      box.disabled = true;
      if (status) status.textContent = "Saving…";
      try {
        var response = await fetch("/renames/" + encodeURIComponent(id) + "/settled", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-PIHTI-Token": ledger.dataset.formToken,
          },
          body: JSON.stringify({ settled: wanted }),
        });
        var result = await response.json();
        if (!response.ok) throw new Error(result.error || "Could not update the ledger");
        box.checked = result.settled;
        var card = box.closest("[data-rename-entry]");
        if (card) card.classList.toggle("is-settled", result.settled);
        if (status) status.textContent = result.settled ? "Settled" : "Reopened";
      } catch (error) {
        box.checked = !wanted;
        if (status) status.textContent = error.message;
      } finally {
        box.disabled = false;
      }
    });
  });

  function filterRenames() {
    var query = search ? search.value.trim().toLowerCase() : "";
    var shown = 0;
    cards.forEach(function (card) {
      var match = !query || card.dataset.search.indexOf(query) !== -1;
      card.hidden = !match;
      if (match) shown += 1;
    });
    if (counter) counter.textContent = String(shown);
    if (empty) empty.hidden = shown !== 0;
  }

  if (search) search.addEventListener("input", filterRenames);
  filterRenames();
})();
