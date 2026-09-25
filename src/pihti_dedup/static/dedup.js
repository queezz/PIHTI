(function () {
  "use strict";

  var host = document.getElementById("dup-results");
  if (!host) return;

  var FILTER_KEY = "pihti-dedup-filter";
  var FILTER_KINDS = { all: true, exact: true, renamed: true };
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
      var fileCount = card.querySelector("[data-group-file-count]");
      if (fileCount) fileCount.textContent = members.length + " files";
      card.querySelectorAll("[data-member-delete]").forEach(function (action) {
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
        var isLeftover = button.dataset.leftover === "true";
        var card = button.closest("[data-group]");
        var row = button.closest(".member");
        var hideWholeCard = card.querySelectorAll(".member").length <= 2;
        if (!window.confirm(isLeftover
          ? "Remove this Inventor save leftover to recoverable quarantine?\n\n" + displayPath +
            "\n\nIdentical original, which stays:\n" + keepPath
          : "Move only this file to recoverable quarantine?\n\n" + displayPath +
            "\n\nRemaining identical file(s):\n" + keepPath +
            "\n\nContinue only after checking Inventor references."
        )) return;
        if (hideWholeCard) {
          card.dataset.operationPending = "true";
          applyFilters();
        } else {
          row.hidden = true;
        }
        showToast("Moving to quarantine: " + displayPath);
        button.disabled = true;
        button.textContent = isLeftover ? "Removing…" : "Deleting…";
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
    resetCleanupContext(restoredMerge && restoredMerge.dataset.planSrc ? restoredMerge : null);
    applyFilters();
    saveFilterState();
    restoreViewportAnchor(viewAnchor);
  }

  loadResults({ includeVendor: filterState.includeVendor });
})();

(function () {
  "use strict";

  // Doctor name session: the reviewed consolidation of different-byte
  // revisions, reached only through its closed disclosure.
  var box = document.querySelector("[data-doctor-consolidate]");
  if (!box) return;
  box.querySelectorAll("[data-consolidate-keep]").forEach(function (button) {
    button.addEventListener("click", async function () {
      var keepPath = button.dataset.displayPath;
      var others = Number(box.dataset.memberCount || "0") - 1;
      if (!window.confirm(
        "Keep this revision and move the other " + others +
        " file(s) with this name to recoverable quarantine?\n\nKEEP:\n" + keepPath +
        "\n\nContinue only because you opened these revisions side by side in Inventor " +
        "and compared them."
      )) return;
      box.querySelectorAll("[data-consolidate-keep]").forEach(function (other) {
        other.disabled = true;
      });
      var original = button.textContent;
      button.textContent = "Moving…";
      try {
        var response = await fetch(box.dataset.consolidateSrc, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-PIHTI-Token": box.dataset.formToken,
          },
          body: JSON.stringify({ keep_path: button.dataset.keepPath, reviewed: true }),
        });
        var result = await response.json();
        if (!response.ok) throw new Error(result.error || "Consolidation failed");
        var target = new URL(box.dataset.done, window.location.href);
        target.searchParams.set("kept", button.dataset.keepPath);
        window.location.assign(target.toString());
      } catch (error) {
        window.alert(error.message);
        box.querySelectorAll("[data-consolidate-keep]").forEach(function (other) {
          other.disabled = false;
        });
        button.textContent = original;
      }
    });
  });
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

  // The rail shows as much of the note (or the root's summary) as its fixed
  // budget holds; a longer text is cut with a fade rather than growing the card.
  function markCuts() {
    document.querySelectorAll("[data-note-rail-body], .rail-context .catalog-description").forEach(function (body) {
      body.classList.toggle("is-cut", body.scrollHeight > body.clientHeight + 1);
    });
  }
  markCuts();
  window.addEventListener("resize", markCuts);

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
    // A sourcing note names its folder, so its attachments preview as saved.
    if (form.dataset.previewFolder) body.append("sourcing", form.dataset.previewFolder);
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

// Mesh tools: the one slim line under every preview that can turn in 3D (the
// inspector's, the part page's, the Enlarge dialog's). Still or 3D, kept for
// every file; which axis is up, Y for an Inventor file (its STEP comes out of
// Inventor Y up) and Z for the rest, a flip kept per file; and a section
// plane across the mesh's box on one of its own axes, for the file shown now.
var PihtiMeshTools = (function () {
  "use strict";

  var VIEW_KEY = "pihti-mesh-view";
  var UP_KEY = "pihti-mesh-up";
  var UP_LIMIT = 500;
  var AXES = { x: 0, y: 1, z: 2 };

  function load(key) {
    try { return localStorage.getItem(key); } catch (_) { return null; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, value); } catch (_) { /* kept for this page only */ }
  }
  // `/mesh/<path>?v=...` names the file; its extension picks the up axis.
  function pathOf(url) {
    var path = String(url || "").split("?")[0].replace(/^\/mesh\//, "");
    try { return decodeURIComponent(path); } catch (_) { return path; }
  }
  function defaultUp(url) { return /\.(ipt|iam)$/i.test(pathOf(url)) ? "y" : "z"; }
  function chosenUps() {
    try {
      var saved = JSON.parse(load(UP_KEY) || "{}");
      return saved && typeof saved === "object" ? saved : {};
    } catch (_) { return {}; }
  }
  function upFor(url) {
    var chosen = chosenUps()[pathOf(url).toLowerCase()];
    return chosen === "y" || chosen === "z" ? chosen : defaultUp(url);
  }
  // Only a flip away from the default is stored; the oldest go past UP_LIMIT.
  function rememberUp(url, axis) {
    if (!url) return;
    var all = chosenUps();
    var key = pathOf(url).toLowerCase();
    delete all[key];
    if (axis !== defaultUp(url)) all[key] = axis;
    var keys = Object.keys(all);
    while (keys.length > UP_LIMIT) delete all[keys.shift()];
    save(UP_KEY, JSON.stringify(all));
  }
  function view() { return load(VIEW_KEY) === "still" ? "still" : "3d"; }
  function rememberView(value) { save(VIEW_KEY, value === "still" ? "still" : "3d"); }

  // A canvas keeps its context for life, lost or given back, so a new viewer
  // needs a new canvas in the old one's place.
  function freshCanvas(old) {
    var fresh = old.cloneNode(false);
    ["style", "width", "height"].forEach(function (name) { fresh.removeAttribute(name); });
    fresh.hidden = true;
    old.replaceWith(fresh);
    return fresh;
  }

  // A section on a mesh axis, hiding the half the eye looks from; the same
  // axis again keeps its place and asks the eye again.
  function section(viewer, previous, axis) {
    if (axis === null || !viewer) return null;
    return {
      axis: axis,
      at: previous && previous.axis === axis ? previous.at : 0.5,
      side: viewer.facing(axis)
    };
  }

  // Wires one tools line to `on.view(value)`, `on.up(axis)`, `on.cut(index or
  // null)` and `on.at(fraction)`; `set(state)` shows `{ idle, view, up,
  // ready, section }` on its buttons. Null without the line (an old page).
  function bind(root, on) {
    if (!root) return null;
    var range = root.querySelector("[data-mesh-cut-at]");
    function each(selector, apply) { Array.prototype.forEach.call(root.querySelectorAll(selector), apply); }
    root.addEventListener("click", function (event) {
      var button = event.target.closest("button");
      if (!button || button.disabled) return;
      if (button.dataset.meshView) on.view(button.dataset.meshView);
      else if (button.dataset.meshUp) on.up(button.dataset.meshUp);
      else if (button.dataset.meshCut) on.cut(button.dataset.meshCut in AXES ? AXES[button.dataset.meshCut] : null);
    });
    if (range) range.addEventListener("input", function () { on.at(Number(range.value) / 100); });
    return {
      set: function (state) {
        var three = state.view !== "still";
        var cut = state.section ? "xyz".charAt(state.section.axis) : "off";
        root.classList.toggle("is-idle", !!state.idle);
        each("[data-mesh-view]", function (button) {
          button.setAttribute("aria-pressed", String(button.dataset.meshView === (three ? "3d" : "still")));
        });
        each("[data-mesh-up]", function (button) {
          button.setAttribute("aria-pressed", String(three && button.dataset.meshUp === state.up));
          button.disabled = !three;
        });
        each("[data-mesh-cut]", function (button) {
          button.setAttribute("aria-pressed", String(three && !!state.ready && button.dataset.meshCut === cut));
          button.disabled = !(three && state.ready);
        });
        if (range) {
          range.disabled = !(three && state.ready && state.section);
          range.value = String((state.section ? state.section.at : 0.5) * 100);
        }
      }
    };
  }

  return {
    upFor: upFor, rememberUp: rememberUp, view: view, rememberView: rememberView,
    freshCanvas: freshCanvas, section: section, bind: bind
  };
})();

// Enlarge: one deliberate modal the reader opens from a shown preview (the
// inspector's or the part page's) and closes with Escape, × or the backdrop.
// It holds one large canvas with the mesh the small view already fetched (no
// second request) under its own camera, up axis and section, starting from
// the small view's, so the small view keeps its own. In Still the still image
// fills it. The large canvas's GL resources go on close, and focus returns to
// the opener.
var PihtiEnlarge = (function () {
  "use strict";

  var V3 = window.PihtiViewer3D;
  var dialog = document.querySelector("dialog[data-mesh-dialog]");
  if (!dialog || !V3) return null;
  var nameLine = dialog.querySelector("[data-mesh-dialog-name]");
  var folderLine = dialog.querySelector("[data-mesh-dialog-folder]");
  var stage = dialog.querySelector("[data-mesh-dialog-stage]");
  var still = dialog.querySelector("[data-mesh-dialog-image]");
  var viewer = null;
  var drawn = false;  // the viewer holds this open's mesh
  var current = null;  // { info, mesh, view, up, section } for this open
  var fetching = null;
  var returnTo = null;
  var sizing = 0;
  var pressedBackdrop = false;
  var tools = PihtiMeshTools.bind(dialog.querySelector("[data-mesh-tools]"), {
    view: function (value) {
      current.view = value;
      if (value === "still") showStill(); else show3D();
    },
    up: function (axis) {
      current.up = axis;
      PihtiMeshTools.rememberUp(current.info.url, axis);
      if (viewer && drawn) viewer.setUp(axis);
      if (current.info.onUp) current.info.onUp(axis);
      sync();
    },
    cut: function (axis) {
      current.section = PihtiMeshTools.section(viewer, current.section, axis);
      if (viewer) viewer.setSection(current.section);
      sync();
    },
    at: function (fraction) {
      if (!current.section || !viewer) return;
      current.section.at = fraction;
      viewer.setSection(current.section);
    }
  });

  function canvas() { return stage.querySelector("canvas"); }
  function sync() {
    if (!tools || !current) return;
    tools.set({ view: current.view, up: current.up, ready: drawn && !canvas().hidden, section: current.section });
  }
  function showStill() {
    canvas().hidden = true;
    if (current && current.info.still) still.src = current.info.still;
    still.hidden = !still.getAttribute("src");
    sync();
  }
  // A lost context: the still until the reader asks for 3D again, then a
  // new viewer on a fresh canvas.
  function dropViewer() {
    if (viewer) viewer.dispose();
    viewer = null;
    drawn = false;
    PihtiMeshTools.freshCanvas(canvas());
  }
  function draw3D() {
    var surface = canvas();
    if (viewer && drawn) {
      still.hidden = true;
      surface.hidden = false;
      sync();
      return;
    }
    if (!viewer) viewer = V3.create(surface, { up: current.up, onLost: function () { dropViewer(); showStill(); } });
    if (viewer) {
      viewer.resize(stage.clientWidth, stage.clientHeight);
      // Synchronous: real pixels exist once this returns.
      if (viewer.show(current.mesh, { up: current.up, section: current.section })) {
        drawn = true;
        still.hidden = true;
        surface.hidden = false;
        sync();
        return;
      }
      dropViewer();
    }
    showStill();
  }
  function show3D() {
    if (current.mesh) { draw3D(); return; }
    showStill();
    if (!current.info.url || fetching) return;
    var mine = current;
    fetching = window.AbortController ? new AbortController() : {};
    V3.fetchMesh(mine.info.url, fetching.signal).then(function (mesh) {
      fetching = null;
      mine.mesh = mesh;
      if (current === mine && dialog.open && mine.view !== "still") draw3D();
    }, function () { fetching = null; });
  }
  // The stage is laid out before the first frame, so the mesh is framed for
  // the size it is shown at; a window resize frames it again, no refetch.
  function fit() {
    sizing = 0;
    if (!viewer || !drawn || !dialog.open) return;
    viewer.resize(stage.clientWidth, stage.clientHeight);
    viewer.home(true);
  }
  window.addEventListener("resize", function () {
    if (dialog.open && viewer && !sizing) sizing = window.requestAnimationFrame(fit);
  });

  // `info`: name, folder, still, and the small view's url, view ("still" or
  // "3d"), up axis and section; `onUp(axis)` hears a flip made here. `mesh`
  // may be null in Still: 3D then fetches it (from the page memo if it can).
  function open(mesh, info, opener) {
    if (dialog.open || (!mesh && !info.url)) return;
    var section = info.section ? { axis: info.section.axis, at: info.section.at, side: info.section.side } : null;
    current = { info: info, mesh: mesh, view: info.view === "still" ? "still" : "3d", up: info.up || "z", section: section };
    returnTo = opener || document.activeElement;
    nameLine.textContent = info.name || "";
    folderLine.textContent = info.folder || "";
    dialog.showModal();
    if (current.view === "still") showStill(); else show3D();
  }

  dialog.addEventListener("close", function () {
    window.cancelAnimationFrame(sizing);
    sizing = 0;
    if (fetching && fetching.abort) fetching.abort();
    fetching = null;
    // Gives the context back; the next open gets a fresh canvas.
    dropViewer();
    current = null;
    still.hidden = true;
    still.removeAttribute("src");
    if (returnTo && returnTo.isConnected) returnTo.focus({ preventScroll: true });
    returnTo = null;
  });
  dialog.querySelectorAll("[data-mesh-dialog-close]").forEach(function (closer) {
    closer.addEventListener("click", function () { dialog.close(); });
  });
  // The backdrop closes it only when the press began there too: a drag that
  // starts on the canvas and ends outside it is still a turn, not a close.
  dialog.addEventListener("pointerdown", function (event) { pressedBackdrop = event.target === dialog; });
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog && pressedBackdrop) dialog.close();
  });

  return { open: open };
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
  var flagBox = inspector && inspector.querySelector("[data-inspector-flags]");
  var flagForms = inspector ? Array.from(inspector.querySelectorAll("form[data-inspector-flag]")) : [];
  var canvas = inspector && inspector.querySelector("[data-inspector-canvas]");
  var meshNote = inspector && inspector.querySelector("[data-inspector-mesh-note]");
  var stepForm = inspector && inspector.querySelector("form[data-inspector-step-export]");
  var enlargeButton = inspector && inspector.querySelector("[data-inspector-enlarge]");
  var tools = inspector && inspector.querySelector("[data-mesh-tools]");
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
    pointFlags(tile, title.textContent);
    empty.hidden = true;
    body.hidden = false;
    shown = tile;
    wantMesh(tile.dataset.mesh || "");
    fitImage();
  }

  // An STL, 3MF, or STEP tile turns in 3D. Only the file the inspector shows
  // is fetched, once it has been shown for MESH_DELAY and only while the card
  // has room for a preview, so walking or hovering across many tiles never
  // queues requests; the still image stays until the mesh arrives and
  // whenever it cannot (a refusal names its reason below the preview). In
  // Still nothing is fetched. A lost GL context shows the still, and the
  // next file gets a new viewer on a fresh canvas.
  var V3 = window.PihtiViewer3D;
  var MESH_DELAY = 150;
  var LARGE_MESH_BYTES = 5 * 1024 * 1024;  // above this, name the download; no spinner
  var viewer = null;
  var meshWanted = "";
  var meshStarted = "";
  var meshTimer = null;
  var meshAbort = null;
  var shownMesh = null;  // the mesh on the canvas now, for Enlarge
  var meshView = tools ? PihtiMeshTools.view() : "3d";  // an old page has no Still to go back from
  var meshUp = "z";
  var section = null;  // the shown file's only; another file starts without
  var toolLine = PihtiMeshTools.bind(tools, {
    view: function (value) {
      meshView = value === "still" ? "still" : "3d";
      PihtiMeshTools.rememberView(meshView);
      if (meshView === "still") {
        stopMesh();
        stillImage();
        meshNote.hidden = true;
        if (stepForm) stepForm.hidden = true;
        fitImage();
      } else {
        scheduleMesh();
      }
      syncTools();
    },
    up: setUp,
    cut: function (axis) {
      if (!viewer || !shownMesh) return;
      section = PihtiMeshTools.section(viewer, section, axis);
      viewer.setSection(section);
      syncTools();
    },
    at: function (fraction) {
      if (!section || !viewer) return;
      section.at = fraction;
      viewer.setSection(section);
    }
  });
  function meshCapable() { return !!(canvas && V3 && V3.supported()); }
  function syncTools() {
    // Enlarge keeps its place and shows only while it has something to show.
    if (enlargeButton) {
      var ready = shownMesh || (meshView === "still" && meshWanted && meshCapable());
      enlargeButton.classList.toggle("is-idle", !ready);
    }
    if (toolLine) {
      toolLine.set({
        idle: !meshWanted || !meshCapable(), view: meshView, up: meshUp,
        ready: !!shownMesh, section: section
      });
    }
  }
  function setUp(axis) {
    meshUp = axis;
    PihtiMeshTools.rememberUp(meshWanted, axis);
    if (viewer && shownMesh) viewer.setUp(axis);
    syncTools();
  }
  function stillImage() {
    if (canvas) canvas.hidden = true;
    image.hidden = false;
    shownMesh = null;
    section = null;
    syncTools();
  }
  function loseViewer() {
    if (viewer) viewer.dispose();
    viewer = null;
    canvas = PihtiMeshTools.freshCanvas(canvas);
    meshStarted = "";  // 3D again, a resize or the next file loads anew
    stillImage();
  }
  function stopMesh() {
    window.clearTimeout(meshTimer);
    meshTimer = null;
    if (meshAbort) meshAbort.abort();
    meshAbort = null;
    meshStarted = "";
    if (viewer) viewer.clear();  // the GPU buffers of the file shown before
  }
  function scheduleMesh() {
    if (meshWanted && meshView === "3d" && !meshStarted && !meshTimer && meshCapable()) {
      meshTimer = window.setTimeout(loadMesh, MESH_DELAY);
    }
  }
  function wantMesh(url) {
    if (!canvas || url === meshWanted) return;
    stopMesh();
    meshWanted = url;
    meshUp = url ? PihtiMeshTools.upFor(url) : "z";
    stillImage();
    meshNote.hidden = true;
    if (stepForm) stepForm.hidden = true;
    scheduleMesh();
  }
  function showLoadingSize(bytes) {
    if (bytes < LARGE_MESH_BYTES) return;
    meshNote.textContent = "Loading 3D · " + Math.round(bytes / (1024 * 1024)) + " MB";
    meshNote.hidden = false;
    fitImage();
  }
  function loadMesh() {
    meshTimer = null;
    var url = meshWanted;
    if (!url || meshView !== "3d" || meshStarted === url || image.parentElement.hidden) return;
    meshStarted = url;
    var controller = window.AbortController ? new AbortController() : null;
    meshAbort = controller;
    V3.fetchMesh(url, controller && controller.signal, showLoadingSize).then(function (mesh) {
      if (meshWanted !== url || meshView !== "3d") return;
      meshAbort = null;
      meshNote.hidden = true;
      if (!viewer) viewer = V3.create(canvas, { up: meshUp, onLost: loseViewer });
      fitImage();  // sizes the still-hidden canvas before the first paint
      if (!viewer) return;
      // Synchronous: real pixels exist once this returns.
      if (viewer.show(mesh, { up: meshUp, section: null })) {
        canvas.hidden = false;
        image.hidden = true;
        shownMesh = mesh;
        syncTools();
      } else {
        loseViewer();
      }
    }, function (error) {
      if (meshWanted !== url || error.name === "AbortError") return;
      meshAbort = null;
      if (stepForm && shown && error.reason === stepForm.dataset.reason) {
        pointStepExport(shown);
        stepForm.hidden = false;
        fitImage();
      } else if (error.reason) {
        meshNote.textContent = "Still image: " + error.reason + ".";
        meshNote.hidden = false;
        fitImage();  // the note takes its line from the card, never the toggles'
      }
    });
  }

  // Enlarge (or F while a tile or the inspector has focus) shows the mesh on
  // the canvas large, or in Still the still image, named with its folder;
  // closing returns to the opener.
  function enlarge(opener) {
    if (!shown || !PihtiEnlarge) return false;
    var still = meshView === "still";
    if (still ? !(meshWanted && meshCapable()) : (!shownMesh || canvas.hidden)) return false;
    window.clearTimeout(hoverTimer);
    var relative = decodeURIComponent((shown.getAttribute("href") || "").replace(/^\/part\//, ""));
    var cut = relative.lastIndexOf("/");
    var url = meshWanted;
    PihtiEnlarge.open(still ? null : shownMesh, {
      name: title.textContent,
      folder: cut > 0 ? relative.slice(0, cut).replace(/\//g, "\\") : "",
      still: image.currentSrc || image.src,
      url: url,
      view: meshView,
      up: meshUp,
      section: section,
      onUp: function (axis) { if (meshWanted === url) setUp(axis); }
    }, opener);
    return true;
  }
  function isEnlargeKey(event) {
    return (event.key === "f" || event.key === "F") &&
      !(event.altKey || event.ctrlKey || event.metaKey || event.shiftKey);
  }
  if (enlargeButton) {
    enlargeButton.addEventListener("click", function () { enlarge(enlargeButton); });
    inspector.addEventListener("keydown", function (event) {
      if (isEnlargeKey(event) && enlarge(event.target)) event.preventDefault();
    });
  }

  // An Inventor file turns from its STEP in the mirror. Without a current
  // one the note's line offers "export now" for the file the inspector
  // names, and for nothing else: a submit for any other file is refused.
  function pointStepExport(tile) {
    var part = tile.getAttribute("href") || "";
    stepForm.action = part + "/step-export";
    stepForm.dataset.file = part;
    var origin = stepForm.querySelector("input[data-origin-from-file]");
    if (origin) {
      var relative = decodeURIComponent(part.replace(/^\/part\//, ""));
      origin.value = relative.indexOf("/") > 0 ? relative.slice(0, relative.lastIndexOf("/")) : ".";
    }
  }
  if (stepForm) {
    stepForm.addEventListener("submit", function (event) {
      if (!shown || !stepForm.dataset.file || stepForm.dataset.file !== shown.getAttribute("href")) {
        event.preventDefault();
      }
    });
  }

  // The two placement toggles act on the file the inspector names, and on
  // nothing else: each form is pointed at that file together with the title,
  // carries the value it wants (so a repeated submit cannot flip it back),
  // and remembers the file so a submit for any other file is refused.
  var FLAG_TEXT = {
    hero: {
      on: "Main assembly · clear",
      off: "Make main assembly",
      setTitle: function (name) { return "Show " + name + " among the Main assemblies and first on its folder cards"; },
      clearTitle: function (name) { return "Stop showing " + name + " among the Main assemblies (asks first)"; },
      confirm: function (name) { return "Clear main assembly on " + name + "? It stays in its folder; only the placement goes."; }
    },
    featured: {
      on: "Cover · clear",
      off: "Use as folder cover",
      setTitle: function (name) { return "Show " + name + " on its folder's card"; },
      clearTitle: function (name) { return "Stop showing " + name + " on its folder's card (asks first)"; },
      confirm: function (name) { return "Stop using " + name + " as its folder's cover?"; }
    }
  };
  function pointFlags(tile, name) {
    var part = tile.getAttribute("href") || "";
    flagForms.forEach(function (form) {
      var key = form.dataset.inspectorFlag;
      var text = FLAG_TEXT[key];
      var on = tile.dataset[key] === "1";
      form.action = part + "/" + key;
      form.dataset.file = part;
      form.dataset.confirm = on ? text.confirm(name) : "";
      form.querySelector('input[name="' + key + '"]').value = on ? "0" : "1";
      var origin = form.querySelector("input[data-origin-from-file]");
      if (origin) {
        // Search results return to the file's own folder, where its tile is.
        var relative = decodeURIComponent(part.replace(/^\/part\//, ""));
        origin.value = relative.indexOf("/") > 0 ? relative.slice(0, relative.lastIndexOf("/")) : ".";
      }
      var button = form.querySelector("button");
      button.textContent = on ? text.on : text.off;
      button.title = on ? text.clearTitle(name) : text.setTitle(name);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }
  flagForms.forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!shown || !form.dataset.file || form.dataset.file !== shown.getAttribute("href")) {
        event.preventDefault();
        return;
      }
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  // The inspector fills the fixed space between the folder card and the
  // legend. Its preview area comes first: PREVIEW_FLOOR tall whenever the
  // card has that much room above the title and the toggles (every window
  // 800px tall or more), then two fact rows, then any room left grows the
  // preview up to a square. The fact list takes what remains and scrolls
  // inside itself; the area keeps one height for every file whose name fits
  // one line, and gives a wrapped name only the lines it needs.
  var PREVIEW_FLOOR = 240;
  var FACT_ROOM = 48;  // two fact rows (a badge row is about 24px)
  var PREVIEW_MIN = 32;  // below this a short window shows no preview at all
  var PREVIEW_MAX = 384;
  function outerHeight(element) {
    if (!element || element.hidden) return 0;
    var style = window.getComputedStyle(element);
    return element.offsetHeight + (parseFloat(style.marginTop) || 0) + (parseFloat(style.marginBottom) || 0);
  }
  function fitImage() {
    if (body.hidden || !inspector.offsetParent) return;
    var padding = parseFloat(window.getComputedStyle(inspector).paddingBottom) || 0;
    var limit = inspector.getBoundingClientRect().bottom - padding;
    // The flags' own top margin is `auto`, so only their box counts.
    var below = outerHeight(tools) + outerHeight(meshNote) + outerHeight(stepForm) + outerHeight(title) +
      (flagBox ? flagBox.offsetHeight : 0);
    var preview = image.parentElement;
    preview.hidden = false;
    var room = Math.floor(limit - preview.getBoundingClientRect().top - below);
    var square = preview.clientWidth || PREVIEW_MAX;
    var height = room - FACT_ROOM >= PREVIEW_FLOOR
      ? Math.min(PREVIEW_MAX, square, room - FACT_ROOM)
      : Math.min(PREVIEW_FLOOR, room);
    preview.hidden = height < PREVIEW_MIN;
    height = Math.max(PREVIEW_MIN, height);
    preview.style.height = height + "px";
    image.style.maxHeight = height + "px";
    // The 3D view fills the preview area: the card's width, the area's height.
    // Sized even while the canvas is still hidden, so the first frame after a
    // swap already has the right dimensions and nothing visibly resizes.
    if (viewer && canvas && !preview.hidden) {
      viewer.resize(preview.clientWidth, height);
    }
    // A window made tall enough to show the preview fetches the waiting mesh.
    if (!preview.hidden) scheduleMesh();
  }
  window.addEventListener("resize", fitImage);

  function clear() {
    window.clearTimeout(hoverTimer);
    if (!inspector) return;
    body.hidden = true;
    empty.hidden = false;
    wantMesh("");
    image.removeAttribute("src");
    facts.replaceChildren();
    flagForms.forEach(function (form) { form.removeAttribute("action"); delete form.dataset.file; });
    if (stepForm) { stepForm.hidden = true; stepForm.removeAttribute("action"); delete stepForm.dataset.file; }
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
    if (isEnlargeKey(event) && tile === shown) {
      if (enlarge(tile)) event.preventDefault();
      return;
    }
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
    // Escape inside a dialog closes that dialog and leaves the inspector be.
    if (event.target.closest && event.target.closest("dialog")) return;
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

  // Part page: an STL, 3MF, STEP or mirrored Inventor file turns in 3D in the
  // still preview's place, at the size the preview was shown at; the image is
  // the fallback, and in Still the only thing shown (no download). A lost GL
  // context shows the still; 3D again builds a new viewer on a fresh canvas.
  var V3 = window.PihtiViewer3D;
  var box = document.querySelector("[data-mesh-viewer]");
  if (!box) return;
  var tools = box.querySelector("[data-mesh-tools]");
  if (!V3 || !V3.supported()) {
    if (tools) tools.hidden = true;
    return;
  }
  var image = box.querySelector("img");
  var canvas = box.querySelector("canvas");
  var note = box.querySelector(".mesh-note");
  var enlargeLine = box.querySelector(".mesh-enlarge-line");
  var enlargeButton = box.querySelector("[data-mesh-enlarge]");
  var url = box.dataset.mesh;
  var meshView = tools ? PihtiMeshTools.view() : "3d";
  var meshUp = PihtiMeshTools.upFor(url);
  var section = null;
  var mesh = null;
  var viewer = null;
  var drawn = false;  // the viewer holds the mesh
  var loading = false;
  var size = null;
  var toolLine = PihtiMeshTools.bind(tools, {
    view: function (value) {
      meshView = value === "still" ? "still" : "3d";
      PihtiMeshTools.rememberView(meshView);
      if (meshView === "still") showStill(); else { sync(); start(); }
    },
    up: function (axis) { setUp(axis); },
    cut: function (axis) {
      if (!viewer || !drawn) return;
      section = PihtiMeshTools.section(viewer, section, axis);
      viewer.setSection(section);
      sync();
    },
    at: function (fraction) {
      if (!section || !viewer) return;
      section.at = fraction;
      viewer.setSection(section);
    }
  });

  function shows3D() { return drawn && !canvas.hidden; }
  function sync() {
    if (toolLine) toolLine.set({ view: meshView, up: meshUp, ready: shows3D(), section: section });
    if (enlargeLine && enlargeButton && PihtiEnlarge) enlargeLine.hidden = !(shows3D() || meshView === "still");
  }
  function setUp(axis) {
    meshUp = axis;
    PihtiMeshTools.rememberUp(url, axis);
    if (viewer && drawn) viewer.setUp(axis);
    sync();
  }
  function showStill() {
    canvas.hidden = true;
    image.hidden = false;
    sync();
  }
  function loseViewer() {
    if (viewer) viewer.dispose();
    viewer = null;
    drawn = false;
    section = null;
    canvas = PihtiMeshTools.freshCanvas(canvas);
    showStill();
  }
  // Measured while the still is on the page; kept for a return from Still.
  function measure() {
    if (!image.hidden && image.offsetWidth) size = [image.offsetWidth, image.offsetHeight || image.offsetWidth];
    return size || [512, 512];
  }
  function swap() {
    if (meshView !== "3d" || !mesh) return;
    if (note) note.hidden = true;
    if (!drawn) {
      var dims = measure();
      if (!viewer) viewer = V3.create(canvas, { up: meshUp, onLost: loseViewer });
      if (!viewer) return;
      viewer.resize(dims[0], dims[1]);
      // Synchronous: real pixels exist once this returns.
      if (!viewer.show(mesh, { up: meshUp, section: section })) { loseViewer(); return; }
      drawn = true;
    }
    canvas.hidden = false;
    image.hidden = true;
    sync();
  }
  function showLoadingSize(bytes) {
    if (!note || bytes < 5 * 1024 * 1024) return;
    note.textContent = "Loading 3D · " + Math.round(bytes / (1024 * 1024)) + " MB";
    note.hidden = false;
  }
  function start() {
    if (meshView !== "3d") return;
    if (mesh) {
      if (image.complete) swap(); else image.addEventListener("load", swap, { once: true });
      return;
    }
    if (loading) return;
    loading = true;
    V3.fetchMesh(url, undefined, showLoadingSize).then(function (result) {
      loading = false;
      mesh = result;
      start();
    }, function (error) {
      loading = false;
      if (error.reason && note) {
        note.textContent = "Still image: " + error.reason + ".";
        note.hidden = false;
      }
    });
  }

  if (enlargeButton && PihtiEnlarge) {
    enlargeButton.addEventListener("click", function () {
      var still = meshView === "still";
      if (!still && !shows3D()) return;
      PihtiEnlarge.open(still ? null : mesh, {
        name: box.dataset.meshName,
        folder: box.dataset.meshFolder,
        still: image.currentSrc || image.src,
        url: url,
        view: meshView,
        up: meshUp,
        section: section,
        onUp: setUp
      }, enlargeButton);
    });
  }
  sync();
  start();
})();

(function () {
  "use strict";

  // Clearing a Main assembly or folder cover on the part page asks first;
  // setting one does not. The inspector's toggles do the same in their own
  // handler, for whichever file they are pointed at.
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
  var SETTLED_KEY = "pihti-rename-settled-filter";
  var search = ledger.querySelector("[data-rename-search]");
  var settledButtons = Array.from(ledger.querySelectorAll("[data-settled-filter]"));
  var settledFilter = "all";
  try {
    var savedFilter = localStorage.getItem(SETTLED_KEY);
    if (savedFilter === "settled" || savedFilter === "unsettled") settledFilter = savedFilter;
  } catch (_) { /* storage disabled — show every rename */ }
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
        if (card) {
          card.classList.toggle("is-settled", result.settled);
          card.dataset.settled = result.settled ? "true" : "false";
        }
        if (status) status.textContent = result.settled ? "Settled" : "Reopened";
        syncSettledCounts();
      } catch (error) {
        box.checked = !wanted;
        if (status) status.textContent = error.message;
      } finally {
        box.disabled = false;
      }
    });
  });

  function syncSettledCounts() {
    var settled = cards.filter(function (card) { return card.dataset.settled === "true"; }).length;
    var settledCount = ledger.querySelector("[data-settled-count]");
    var unsettledCount = ledger.querySelector("[data-unsettled-count]");
    if (settledCount) settledCount.textContent = String(settled);
    if (unsettledCount) unsettledCount.textContent = String(cards.length - settled);
  }

  function filterRenames() {
    var query = search ? search.value.trim().toLowerCase() : "";
    var shown = 0;
    cards.forEach(function (card) {
      var settled = card.dataset.settled === "true";
      var match = (!query || card.dataset.search.indexOf(query) !== -1) &&
        (settledFilter === "all" || (settledFilter === "settled") === settled);
      card.hidden = !match;
      if (match) shown += 1;
    });
    if (counter) counter.textContent = String(shown);
    if (empty) empty.hidden = shown !== 0;
  }

  function selectSettled(value) {
    settledFilter = value;
    settledButtons.forEach(function (button) {
      var active = button.dataset.settledFilter === value;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    try { localStorage.setItem(SETTLED_KEY, value); }
    catch (_) { /* the filter still holds for this visit */ }
    filterRenames();
  }

  settledButtons.forEach(function (button) {
    button.addEventListener("click", function () { selectSettled(button.dataset.settledFilter); });
  });
  if (search) search.addEventListener("input", filterRenames);
  selectSettled(settledFilter);
})();

(function () {
  "use strict";

  // Instant filter over what the catalog page already shows, the same
  // mechanics as the Duplicates `data-filter-search` box: no request, one
  // animation frame, Escape clears, nothing persisted. Enter still submits the
  // form, which is the server-side search of the whole archive.
  var input = document.querySelector("input[data-filter-search]");
  var grid = document.querySelector("[data-thumb-grid], [data-filter-list]");
  if (!input) return;
  var archive = document.querySelector("[data-search-archive]");
  var items = grid ? Array.from(grid.querySelectorAll("a.folder-card, a.thumb-tile, [data-filter-item]")) : [];
  // Sourcing pages: the Status card narrows the same list the text does.
  var statusButtons = Array.from(document.querySelectorAll("[data-status-filter]"));
  var groups = grid ? Array.from(grid.querySelectorAll("[data-filter-group]")) : [];
  var status = "";
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
      var match = (!needle || haystacks[index].indexOf(needle) !== -1) &&
        (!status || item.dataset.status === status);
      item.hidden = !match;
      // A main-assembly tile sits in a card with its folder links.
      var card = item.closest(".hero-card");
      if (card) card.hidden = !match;
      if (match) shown += 1;
      if (match && item.matches("a.thumb-tile")) files += 1;
    });
    groups.forEach(function (group) {
      group.hidden = !group.querySelector("[data-filter-item]:not([hidden])");
    });
    if (count) {
      count.textContent = needle ? files + " of " + count.dataset.total : count.dataset.total;
    }
    if (empty) empty.hidden = !(needle || status) || shown !== 0 || !items.length;
    if (archive) archive.hidden = !input.value.trim();
  }

  statusButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      status = button.dataset.statusFilter || "";
      statusButtons.forEach(function (other) {
        other.setAttribute("aria-pressed", other === button ? "true" : "false");
      });
      applyFilter();
    });
  });

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

(function () {
  "use strict";

  // Sourcing notes: paste or drop a picture or a PDF into the note's text.
  // Each file is posted to the folder's attach route, which saves it under
  // `sourcing/attachments/` with a timestamped name and answers with the
  // Markdown embed; that embed goes in at the cursor. The same shape as
  // PIHTI Log's paste-to-attach; nothing is kept in the browser.
  var input = document.querySelector("textarea[data-attach-input]");
  if (!input || !window.fetch) return;
  var form = input.closest("form");
  var token = form && form.querySelector('input[name="token"]');
  var status = document.querySelector("[data-attach-status]");
  var LIMIT = 25 * 1024 * 1024;
  var ALLOWED = /^(image\/(png|jpeg|webp|gif|svg\+xml)|application\/pdf)$/;
  var queue = Promise.resolve();

  function say(text) {
    if (status) status.textContent = text;
  }

  function insert(text) {
    var start = input.selectionStart;
    var end = input.selectionEnd;
    var before = input.value.slice(0, start);
    var after = input.value.slice(end);
    // Each embed is its own paragraph: a blank line before and after it.
    var lead = !before || /\n\n$/.test(before) ? "" : /\n$/.test(before) ? "\n" : "\n\n";
    var tail = /^\n\n/.test(after) ? "" : /^\n/.test(after) ? "\n" : "\n\n";
    var chunk = lead + text + tail;
    input.value = before + chunk + after;
    input.selectionStart = input.selectionEnd = before.length + chunk.length;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function upload(file) {
    var name = file.name || "pasted";
    if (!ALLOWED.test(file.type)) {
      say("Not attached: " + name + ". Pictures (PNG, JPEG, WebP, GIF, SVG) and PDFs only.");
      return Promise.resolve();
    }
    if (file.size > LIMIT) {
      say("Not attached: " + name + " is larger than 25 MB.");
      return Promise.resolve();
    }
    say("Attaching " + name + "…");
    var body = new FormData();
    body.append("file", file, name);
    return fetch(input.dataset.attachUrl, {
      method: "POST",
      body: body,
      headers: { "X-PIHTI-Token": token ? token.value : "" },
      credentials: "same-origin"
    })
      .then(function (response) {
        return response.text().then(function (text) {
          var result = null;
          try { result = JSON.parse(text); } catch (_) { result = null; }
          if (!response.ok || !result || !result.embed) {
            throw new Error((result && result.error) || text || response.statusText);
          }
          return result;
        });
      })
      .then(function (result) {
        insert(result.embed);
        say("Attached " + result.name);
      })
      .catch(function (error) {
        say("Not attached: " + name + ". " + error.message);
      });
  }

  function take(files) {
    files.forEach(function (file) {
      queue = queue.then(function () { return upload(file); });
    });
  }

  input.addEventListener("paste", function (event) {
    var files = Array.from(event.clipboardData ? event.clipboardData.files : []);
    if (!files.length) return;  // plain text pastes as text
    event.preventDefault();
    take(files);
  });
  input.addEventListener("dragover", function (event) {
    if (event.dataTransfer && Array.from(event.dataTransfer.types || []).indexOf("Files") !== -1) {
      event.preventDefault();
      event.dataTransfer.dropEffect = "copy";
    }
  });
  input.addEventListener("drop", function (event) {
    var files = Array.from(event.dataTransfer ? event.dataTransfer.files : []);
    if (!files.length) return;
    event.preventDefault();
    input.focus();
    take(files);
  });
})();

(function () {
  "use strict";

  // The save toast belongs to the save that just ran, not to the address.
  var toast = document.querySelector("[data-sourcing-toast]");
  if (!toast) return;
  var url = new URL(window.location.href);
  url.searchParams.delete("saved");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
  window.setTimeout(function () { toast.remove(); }, 8000);
})();
