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

  // A folder note opens as a reader; Edit swaps in the editor and back.
  function setView(dialog, view) {
    var reader = dialog.querySelector("[data-note-reader]");
    var editor = dialog.querySelector("[data-note-editor]");
    var toggle = dialog.querySelector("[data-note-edit]");
    if (!reader || !editor || !toggle) return;
    var editing = view === "editor";
    dialog.dataset.noteView = editing ? "editor" : "reader";
    reader.hidden = editing;
    editor.hidden = !editing;
    toggle.textContent = editing ? "Read" : "Edit";
    toggle.setAttribute("aria-pressed", editing ? "true" : "false");
    if (editing) {
      var input = editor.querySelector("textarea");
      if (input) input.focus({ preventScroll: true });
    }
  }

  document.querySelectorAll("[data-dialog-open]").forEach(function (opener) {
    opener.addEventListener("click", function () {
      var dialog = document.getElementById(opener.dataset.dialogOpen);
      if (!dialog || dialog.open) return;
      dialog.showModal();
      if (opener.dataset.noteView) setView(dialog, opener.dataset.noteView);
    });
  });

  document.querySelectorAll("[data-note-edit]").forEach(function (toggle) {
    toggle.addEventListener("click", function () {
      var dialog = toggle.closest("dialog");
      if (dialog) setView(dialog, dialog.dataset.noteView === "editor" ? "reader" : "editor");
    });
  });

  // The rail shows as much of the note as its fixed budget holds; a longer
  // note is cut with a fade rather than growing the card.
  document.querySelectorAll("[data-note-rail-body]").forEach(function (body) {
    body.classList.toggle("is-cut", body.scrollHeight > body.clientHeight + 1);
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

  // When an opened branch makes the tree taller than its pinned card, the tree
  // scrolls inside the card; bring the current folder into that view. Only the
  // tree's own scrollTop moves, never the page.
  var current = tree.querySelector("[aria-current]");
  if (current && tree.scrollHeight > tree.clientHeight + 1) {
    var row = current.closest(".tree-row") || current;
    var top = row.offsetTop;
    if (top < tree.scrollTop || top + row.offsetHeight > tree.scrollTop + tree.clientHeight) {
      tree.scrollTop = Math.max(0, top - tree.clientHeight / 3);
    }
  }
})();

(function () {
  "use strict";

  // Duplicates and Doctor link to `/part/...#rename`; open that disclosure.
  var rename = document.querySelector("[data-rename-disclosure]");
  if (rename && window.location.hash === "#rename") rename.open = true;
})();

(function () {
  "use strict";

  // Inspector: a stationary card in the left rail shows the hovered or
  // keyboard-focused tile: its preview at native size (never upscaled) and the
  // facts the server rendered into the tile's hidden <dl>. Nothing floats over
  // the grid. The last tile stays shown when the pointer leaves, so it can be
  // read; Escape clears it. Tiles stay plain links, so Enter opens the part.
  var grid = document.querySelector("[data-thumb-grid]");
  if (!grid) return;

  var TILE = "a.thumb-tile, a.folder-card";
  var HOVER_DELAY = 150;
  var inspector = document.querySelector("[data-inspector]");
  var empty = inspector && inspector.querySelector("[data-inspector-empty]");
  var body = inspector && inspector.querySelector("[data-inspector-body]");
  var image = inspector && inspector.querySelector("[data-inspector-image]");
  var title = inspector && inspector.querySelector("[data-inspector-title]");
  var facts = inspector && inspector.querySelector("[data-inspector-facts]");
  var shown = null;
  var hoverTimer = null;

  // Native size, never upscaled: a small embedded preview stays small.
  function sizeImage(natural) {
    var ratio = window.devicePixelRatio || 1;
    image.style.maxWidth = natural ? natural / ratio + "px" : "";
  }
  if (image) {
    image.addEventListener("load", function () { sizeImage(image.naturalWidth); });
  }

  function show(tile) {
    if (!inspector || !tile.matches("a.thumb-tile")) return;
    var source = tile.querySelector("img");
    if (!source) return;
    var details = tile.querySelector(".thumb-details");
    var name = tile.querySelector(".thumb-name, .hero-name");
    var size = tile.querySelector(".thumb-meta");
    title.textContent = name ? name.textContent : "";
    if (details) {
      var copy = details.cloneNode(true);
      copy.hidden = false;
      facts.replaceChildren(copy);
    } else {
      var line = document.createElement("p");
      line.className = "inspector-plain";
      line.textContent = size ? size.textContent : "";
      facts.replaceChildren(line);
    }
    image.src = source.currentSrc || source.src;
    sizeImage(source.complete ? source.naturalWidth : 0);
    empty.hidden = true;
    body.hidden = false;
    fitImage();
    shown = tile;
  }

  // The rail is capped at the viewport and the folder note above keeps a
  // fixed budget, so the preview takes only the room the rail has left above
  // the title and a couple of fact lines; a short window never pushes the
  // shown file out of the rail.
  var FACT_ROOM = 72;
  var PREVIEW_MAX = 384;
  function fitImage() {
    var rail = inspector.closest(".rail-context");
    if (!rail || body.hidden || !inspector.offsetParent) return;
    var gap = parseFloat(window.getComputedStyle(rail).rowGap) || 0;
    var below = 0;  // the cards under the inspector, such as the legend
    for (var card = inspector.nextElementSibling; card; card = card.nextElementSibling) {
      below += card.offsetHeight + gap;
    }
    var cap = parseFloat(window.getComputedStyle(rail).maxHeight) || rail.clientHeight;
    var limit = rail.getBoundingClientRect().top + cap - below;
    var room = limit - image.getBoundingClientRect().top - FACT_ROOM;
    image.style.maxHeight = Math.max(64, Math.min(PREVIEW_MAX, Math.floor(room))) + "px";
  }
  window.addEventListener("resize", fitImage);

  function clear() {
    window.clearTimeout(hoverTimer);
    if (!inspector) return;
    body.hidden = true;
    empty.hidden = false;
    image.removeAttribute("src");
    facts.replaceChildren();
    shown = null;
  }

  function tiles() {
    return Array.from(grid.querySelectorAll(TILE)).filter(function (tile) { return !tile.hidden; });
  }

  function verticalNeighbour(tile, direction) {
    var from = tile.getBoundingClientRect();
    var centre = from.left + from.width / 2;
    var best = null;
    var bestRow = null;
    var bestDistance = Infinity;
    tiles().forEach(function (candidate) {
      if (candidate === tile) return;
      var box = candidate.getBoundingClientRect();
      var beyond = direction > 0 ? box.top >= from.bottom - 1 : box.bottom <= from.top + 1;
      if (!beyond) return;
      var distance = Math.abs(box.left + box.width / 2 - centre);
      var closerRow = bestRow === null ||
        (direction > 0 ? box.top < bestRow - 1 : box.top > bestRow + 1);
      if (closerRow) {
        bestRow = box.top;
        best = candidate;
        bestDistance = distance;
      } else if (Math.abs(box.top - bestRow) <= 1 && distance < bestDistance) {
        best = candidate;
        bestDistance = distance;
      }
    });
    return best;
  }

  function neighbour(tile, key) {
    var list = tiles();
    var index = list.indexOf(tile);
    if (key === "ArrowRight") return list[index + 1] || null;
    if (key === "ArrowLeft") return index > 0 ? list[index - 1] : null;
    if (key === "ArrowDown") return verticalNeighbour(tile, 1);
    if (key === "ArrowUp") return verticalNeighbour(tile, -1);
    if (key === "Home") return list[0] || null;
    if (key === "End") return list[list.length - 1] || null;
    return null;
  }

  grid.addEventListener("keydown", function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    var tile = event.target.closest(TILE);
    if (!tile) return;
    if (event.key === "Escape") {
      if (shown) {
        event.preventDefault();
        clear();
      }
      return;
    }
    var next = neighbour(tile, event.key);
    if (!next) return;
    event.preventDefault();
    next.focus({ preventScroll: true });
    next.scrollIntoView({ block: "nearest" });
    show(next);
  });

  grid.addEventListener("mouseover", function (event) {
    var tile = event.target.closest(TILE);
    if (!tile || tile === shown) return;
    window.clearTimeout(hoverTimer);
    hoverTimer = window.setTimeout(function () { show(tile); }, HOVER_DELAY);
  });

  grid.addEventListener("mouseout", function (event) {
    var tile = event.target.closest(TILE);
    if (!tile || (event.relatedTarget && tile.contains(event.relatedTarget))) return;
    window.clearTimeout(hoverTimer);  // the last shown tile stays readable
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && shown) clear();
  });

  // A link to `#file-...` lands on that tile: focus it and show it.
  var landed = window.location.hash.indexOf("#file-") === 0 &&
    document.getElementById(window.location.hash.slice(1));
  if (landed && grid.contains(landed) && landed.matches(TILE)) {
    landed.focus({ preventScroll: true });
    show(landed);
  }
})();

(function () {
  "use strict";

  // Clearing a Main assembly or Featured flag on the part page asks first;
  // setting one does not.
  document.querySelectorAll("form[data-flag-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.flagConfirm)) event.preventDefault();
    });
  });
})();

(function () {
  "use strict";

  // The hero toast belongs to the press that just ran, not to the address: a
  // reload or a later Back must not announce it again.
  var toast = document.querySelector("[data-hero-toast]");
  if (!toast) return;
  var url = new URL(window.location.href);
  url.searchParams.delete("hero");
  url.searchParams.delete("featured");
  url.searchParams.delete("file");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  window.setTimeout(function () { toast.remove(); }, 8000);
})();

(function () {
  "use strict";

  // Prefetch a catalog page once the pointer rests on its link. Catalog pages
  // are cacheable for five seconds (see `no_store` in web.py), so the click
  // that follows is served from the browser cache.
  var LINKS = ".folder-tree a.tree-name, .breadcrumbs a, a.folder-card, " +
    "a.hero-folder, a.hero-open-folder";
  var DELAY = 100;
  if (!document.querySelector(LINKS) || !window.fetch) return;
  if (navigator.connection && navigator.connection.saveData) return;

  var requested = new Set();
  var timer = null;

  function prefetch(link) {
    var url = new URL(link.href, window.location.href);
    if (url.origin !== window.location.origin) return;
    if (url.pathname !== "/catalog" && url.pathname.indexOf("/catalog/") !== 0) return;
    if (url.searchParams.has("q") || url.searchParams.has("saved")) return;
    var key = url.pathname + url.search;
    if (requested.has(key) || key === window.location.pathname + window.location.search) return;
    requested.add(key);
    fetch(url.toString(), { credentials: "same-origin" })
      .then(function (response) { return response.text(); })
      .catch(function () { requested.delete(key); });
  }

  document.addEventListener("mouseover", function (event) {
    var link = event.target.closest && event.target.closest(LINKS);
    if (!link) return;
    window.clearTimeout(timer);
    timer = window.setTimeout(function () { prefetch(link); }, DELAY);
  });

  document.addEventListener("mouseout", function (event) {
    var link = event.target.closest && event.target.closest(LINKS);
    if (!link || (event.relatedTarget && link.contains(event.relatedTarget))) return;
    window.clearTimeout(timer);
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

(function () {
  "use strict";

  // Instant filter over what the catalog page already shows, the same
  // mechanics as the Duplicates `data-filter-search` box: no request, one
  // animation frame, Escape clears, nothing persisted. Enter still submits the
  // form, which is the server-side search of the whole archive.
  var input = document.querySelector("input[data-filter-search]");
  var grid = document.querySelector("[data-thumb-grid]");
  if (!input) return;
  var archive = document.querySelector("[data-search-archive]");
  var items = grid ? Array.from(grid.querySelectorAll("a.folder-card, a.thumb-tile")) : [];
  var haystacks = items.map(function (item) {
    return ((item.getAttribute("title") || "") + " " + item.textContent).toLowerCase();
  });
  var count = document.querySelector("[data-filter-count]");
  var empty = document.querySelector("[data-filter-empty]");
  var frame = 0;

  function applyFilter() {
    frame = 0;
    var needle = input.value.trim().toLowerCase();
    var files = 0;
    var shown = 0;
    items.forEach(function (item, index) {
      var match = !needle || haystacks[index].indexOf(needle) !== -1;
      item.hidden = !match;
      // A main-assembly tile sits in a card with its folder links.
      var card = item.parentElement && item.parentElement.classList.contains("hero-card")
        ? item.parentElement : null;
      if (card) card.hidden = !match;
      if (match) shown += 1;
      if (match && item.matches("a.thumb-tile")) files += 1;
    });
    if (count) {
      count.textContent = needle ? files + " of " + count.dataset.total : count.dataset.total;
    }
    if (empty) empty.hidden = !needle || shown !== 0 || !items.length;
    if (archive) archive.hidden = !input.value.trim();
  }

  input.addEventListener("input", function () {
    // A hidden page gets no animation frames; filter at once rather than
    // leave a frame pending that would swallow every later keystroke.
    if (document.visibilityState !== "visible") {
      applyFilter();
      return;
    }
    if (frame) window.cancelAnimationFrame(frame);
    frame = window.requestAnimationFrame(applyFilter);
  });
  input.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && input.value) {
      event.preventDefault();
      input.value = "";
      applyFilter();
    }
  });
  applyFilter();
})();

(function () {
  "use strict";

  // Standard parts: one confirmed action per row, and a per-tab Skip that
  // moves a row into the Skipped group instead of removing it from the page.
  var page = document.querySelector("[data-standard-parts]");
  if (!page) return;

  var SKIP_KEY = "pihti-standard-skipped";
  var skippedSection = page.querySelector("[data-standard-skipped]");
  var skippedList = page.querySelector("[data-standard-skipped-list]");
  var skippedNav = document.querySelector("[data-standard-skipped-nav]");

  function readSkipped() {
    try {
      var value = JSON.parse(window.sessionStorage.getItem(SKIP_KEY) || "[]");
      return Array.isArray(value) ? value : [];
    } catch (_) {
      return [];
    }
  }

  function writeSkipped(paths) {
    try {
      window.sessionStorage.setItem(SKIP_KEY, JSON.stringify(paths));
    } catch (_) {
      // Private windows may refuse storage; skipping still works for this view.
    }
  }

  function setCount(key, value) {
    document.querySelectorAll('[data-standard-nav-count="' + key + '"]').forEach(function (node) {
      node.textContent = value;
    });
  }

  function refreshCounts() {
    page.querySelectorAll("[data-standard-group]").forEach(function (group) {
      var count = group.querySelectorAll("[data-standard-row]").length;
      group.querySelector("[data-standard-group-count]").textContent = count;
      setCount(group.dataset.standardGroup, count);
    });
    var skipped = skippedList.querySelectorAll("[data-standard-row]").length;
    page.querySelector("[data-standard-skipped-count]").textContent = skipped;
    setCount("skipped", skipped);
    skippedSection.hidden = skipped === 0;
    if (skippedNav) skippedNav.hidden = skipped === 0;
  }

  function insertInOrder(list, row) {
    var order = Number(row.dataset.order);
    var next = Array.from(list.querySelectorAll("[data-standard-row]")).find(function (item) {
      return Number(item.dataset.order) > order;
    });
    list.insertBefore(row, next || null);
  }

  function skip(row) {
    insertInOrder(skippedList, row);
    row.classList.add("is-skipped");
    var button = row.querySelector("[data-standard-skip]");
    button.textContent = "Restore";
    button.setAttribute("aria-pressed", "true");
  }

  function restore(row) {
    var home = page.querySelector(
      '[data-standard-group="' + row.dataset.home + '"] [data-standard-list]'
    );
    if (!home) return;
    insertInOrder(home, row);
    row.classList.remove("is-skipped");
    var button = row.querySelector("[data-standard-skip]");
    button.textContent = "Skip";
    button.setAttribute("aria-pressed", "false");
  }

  var remembered = readSkipped();
  page.querySelectorAll("[data-standard-row]").forEach(function (row) {
    if (remembered.indexOf(row.dataset.path) !== -1) skip(row);
  });
  // Forget paths that are no longer on the page (moved, or no longer candidates).
  writeSkipped(remembered.filter(function (path) {
    return !!skippedList.querySelector('[data-path="' + CSS.escape(path) + '"]');
  }));
  refreshCounts();

  page.addEventListener("click", function (event) {
    var button = event.target.closest("[data-standard-skip]");
    if (!button) return;
    var row = button.closest("[data-standard-row]");
    var paths = readSkipped().filter(function (path) { return path !== row.dataset.path; });
    if (row.classList.contains("is-skipped")) {
      restore(row);
    } else {
      skip(row);
      paths.push(row.dataset.path);
    }
    writeSkipped(paths);
    refreshCounts();
  });

  page.querySelectorAll("form[data-standard-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.confirm(form.dataset.standardConfirm)) {
        event.preventDefault();
        return;
      }
      var submit = form.querySelector("button[type=submit]");
      if (submit) {
        submit.disabled = true;
        submit.textContent = submit.dataset.busyLabel || submit.textContent;
      }
    });
  });

  var toast = document.querySelector("[data-operation-toast]");
  if (toast) {
    // The toast belongs to the action that just ran, not to the address: a
    // reload or a later Back must not announce the same move again.
    window.history.replaceState(null, "", window.location.pathname + window.location.hash);
    window.setTimeout(function () { toast.remove(); }, 10000);
  }
})();
