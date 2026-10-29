// FieldOps Nexus UI behaviour. Business rules live on the server; this file only enhances.
(function () {
  // Confirmation dialogs: <button data-confirm="Message" data-confirm-title="Title">
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-confirm]");
    if (!btn || btn.dataset.confirmed === "1") return;
    ev.preventDefault();
    var dlg = document.getElementById("fx-confirm");
    document.getElementById("fx-confirm-title").textContent = btn.dataset.confirmTitle || "Please confirm";
    document.getElementById("fx-confirm-text").textContent = btn.dataset.confirm;
    dlg.returnValue = "";
    dlg.addEventListener("close", function onClose() {
      dlg.removeEventListener("close", onClose);
      if (dlg.returnValue === "ok") {
        btn.dataset.confirmed = "1";
        if (btn.form && btn.form.requestSubmit) { btn.form.requestSubmit(btn); } else { btn.click(); }
      }
    });
    dlg.showModal();
  });

  // Drawer: <button data-drawer-open="id"> / <button data-drawer-close>
  document.addEventListener("click", function (ev) {
    var open = ev.target.closest("[data-drawer-open]");
    if (open) { var d = document.getElementById(open.dataset.drawerOpen); if (d) d.hidden = false; }
    if (ev.target.closest("[data-drawer-close]")) {
      var host = ev.target.closest(".fx-drawer"); if (host) host.hidden = true;
    }
  });

  // Close search results when clicking elsewhere
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest(".fx-search")) {
      var r = document.getElementById("fx-search-results"); if (r) r.innerHTML = "";
    }
  });
})();

/* Delegated handlers (replace inline onclick attributes so the Content-Security-Policy can forbid them). */
document.addEventListener("click", function (e) {
  var nav = e.target.closest("[data-fx-toggle-nav]");
  if (nav) { var l = document.getElementById("fx-layout"); if (l) l.classList.toggle("fx-nav-open"); return; }
  if (e.target.closest("[data-fx-print]")) window.print();
});

// Close mobile navigation drawer on Escape key
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") {
    var l = document.getElementById("fx-layout");
    if (l && l.classList.contains("fx-nav-open")) {
      l.classList.remove("fx-nav-open");
    }
  }
});

/* Asset form: choosing another category reloads the page with the typed values so the category's custom attributes
   appear (the server builds and validates those fields). */
document.addEventListener("change", function (e) {
  var sel = e.target.closest("select[data-category-reload]");
  if (!sel || !sel.form) return;
  var params = new URLSearchParams();
  new FormData(sel.form).forEach(function (value, key) {
    if (typeof value === "string" && key !== "csrfmiddlewaretoken" && key.indexOf("attr_") !== 0 && value !== "") {
      params.set(key, value);
    }
  });
  window.location.search = params.toString();
});

/* Universal FieldOps Nexus Toast & Notification System */
window.fxDismissToast = function (item) {
  if (!item || item.getAttribute('data-dismissing') === '1') return;
  item.setAttribute('data-dismissing', '1');
  item.style.transition = 'opacity 0.3s ease, max-height 0.35s ease, margin 0.35s ease, padding 0.35s ease';
  item.style.opacity = '0';
  item.style.maxHeight = item.offsetHeight + 'px';
  item.offsetHeight; // trigger reflow
  item.style.maxHeight = '0px';
  item.style.marginTop = '0px';
  item.style.marginBottom = '0px';
  item.style.paddingTop = '0px';
  item.style.paddingBottom = '0px';
  item.style.overflow = 'hidden';
  setTimeout(function () {
    if (item && item.parentNode) {
      var parent = item.closest('.fx-toast-container');
      item.remove();
      if (parent && parent.children.length === 0) parent.remove();
    }
  }, 360);
};

window.initToastElement = function (el) {
  if (!el || el.getAttribute('data-dismiss-queued') === '1') return;
  el.setAttribute('data-dismiss-queued', '1');
  var timeoutMs = parseInt(el.getAttribute('data-auto-dismiss') || '4000', 10);
  var timer = null;
  var remaining = timeoutMs;
  var start = Date.now();

  function startTimer() {
    start = Date.now();
    timer = setTimeout(function () {
      window.fxDismissToast(el);
    }, remaining);
  }

  function pauseTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
      remaining -= (Date.now() - start);
      if (remaining < 400) remaining = 400;
    }
  }

  startTimer();
  el.addEventListener('mouseenter', pauseTimer);
  el.addEventListener('mouseleave', startTimer);

  var closeBtn = el.querySelector('.btn-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', function (e) {
      e.preventDefault();
      window.fxDismissToast(el);
    });
  }
};

window.fxToast = function (message, type) {
  if (!message) return;
  type = type || 'success';
  if (type === 'error') type = 'danger';

  var container = document.querySelector('.fx-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'fx-toast-container mb-3';
    container.setAttribute('role', 'status');
    container.setAttribute('aria-live', 'polite');
    var main = document.getElementById('main') || document.querySelector('main') || document.body;
    main.prepend(container);
  }

  var iconHtml = '';
  if (type === 'danger') {
    iconHtml = '<span class="fx-toast-icon text-danger" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg></span>';
  } else if (type === 'warning') {
    iconHtml = '<span class="fx-toast-icon text-warning" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></span>';
  } else if (type === 'info') {
    iconHtml = '<span class="fx-toast-icon text-info" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg></span>';
  } else {
    iconHtml = '<span class="fx-toast-icon text-success" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg></span>';
  }

  var timeoutMs = (type === 'danger' || type === 'warning') ? 6000 : 4500;
  var toast = document.createElement('div');
  toast.className = 'alert alert-' + type + ' fx-toast-message alert-dismissible fade show d-flex align-items-center justify-content-between py-2 px-3 mb-2 shadow-sm';
  toast.setAttribute('role', 'alert');
  toast.setAttribute('data-auto-dismiss', timeoutMs.toString());
  
  toast.innerHTML = '<div class="d-flex align-items-center gap-2 flex-grow-1">' +
    iconHtml +
    '<span class="fx-toast-text">' + message + '</span>' +
    '</div>' +
    '<button type="button" class="btn-close ms-3 p-1" data-bs-dismiss="alert" aria-label="Close" style="font-size: 0.75rem; flex-shrink: 0;"></button>';

  container.appendChild(toast);
  window.initToastElement(toast);
};

function showWorkOrderMessage(message, isError) {
  window.fxToast(message, isError ? 'danger' : 'success');
}

/* Event listeners for live module updates */
document.body.addEventListener("workOrderChanged", function (event) {
  var msg = (event.detail && event.detail.message) || "Work order updated successfully.";
  window.fxToast(msg, "success");
});
document.body.addEventListener("workOrderActionError", function (event) {
  var msg = (event.detail && event.detail.message) || "Work order action failed. Refresh and retry.";
  window.fxToast(msg, "danger");
});
document.body.addEventListener("siteSaved", function (evt) {
  var msg = (evt.detail && evt.detail.message) || "Site record saved successfully.";
  window.fxToast(msg, "success");
});
document.body.addEventListener("assetSaved", function (evt) {
  var msg = (evt.detail && evt.detail.message) || "Asset record saved successfully.";
  window.fxToast(msg, "success");
});
document.body.addEventListener("checklistSaved", function (evt) {
  var msg = (evt.detail && evt.detail.message) || "Checklist protocol saved successfully.";
  window.fxToast(msg, "success");
});
document.body.addEventListener("planSaved", function (evt) {
  var msg = (evt.detail && evt.detail.message) || "Maintenance plan saved successfully.";
  window.fxToast(msg, "success");
});
document.body.addEventListener("partSaved", function (evt) {
  var msg = (evt.detail && evt.detail.message) || "Part inventory record saved successfully.";
  window.fxToast(msg, "success");
});
document.body.addEventListener("showMessage", function (evt) {
  if (evt.detail && evt.detail.message) {
    window.fxToast(evt.detail.message, evt.detail.type || "success");
  }
});


/* Interactive Hierarchy Hub & Tree Controls */
document.addEventListener("DOMContentLoaded", function () {
  // Tree Node Expand / Collapse Toggle
  document.addEventListener("click", function (e) {
    var expander = e.target.closest(".fx-tree-expander");
    if (!expander) return;
    var nodeItem = expander.closest(".fx-tree-node-item");
    if (!nodeItem) return;
    var branch = nodeItem.querySelector(":scope > .fx-tree-branch");
    if (!branch) return;

    var isHidden = branch.style.display === "none";
    branch.style.display = isHidden ? "" : "none";
    expander.classList.toggle("collapsed", !isHidden);
    expander.textContent = isHidden ? "▼" : "▶";
  });

  // Expand All / Collapse All / Toggle Density
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action]");
    if (!btn) return;
    var action = btn.dataset.action;
    var wrapper = document.querySelector(".fx-hierarchy-wrapper");
    if (!wrapper) return;

    if (action === "toggle-density") {
      wrapper.classList.toggle("is-compact");
    } else if (action === "expand-all") {
      wrapper.querySelectorAll(".fx-tree-branch").forEach(function (b) { b.style.display = ""; });
      wrapper.querySelectorAll(".fx-tree-expander").forEach(function (exp) {
        if (!exp.classList.contains("opacity-25")) {
          exp.classList.remove("collapsed");
          exp.textContent = "▼";
        }
      });
    } else if (action === "collapse-all") {
      wrapper.querySelectorAll(".fx-tree-branch").forEach(function (b) { b.style.display = "none"; });
      wrapper.querySelectorAll(".fx-tree-expander").forEach(function (exp) {
        if (!exp.classList.contains("opacity-25")) {
          exp.classList.add("collapsed");
          exp.textContent = "▶";
        }
      });
    }
  });

  // Role Filtering Pills
  document.addEventListener("click", function (e) {
    var pill = e.target.closest("[data-filter-role]");
    if (!pill) return;
    var group = pill.closest(".fx-filter-pill-group");
    if (!group) return;
    group.querySelectorAll(".fx-filter-pill").forEach(function (p) { p.classList.remove("active"); });
    pill.classList.add("active");

    var role = pill.dataset.filterRole; // 'all', 'assembly', 'component', 'replaceable'
    var cards = document.querySelectorAll(".fx-tree-node-card");
    cards.forEach(function (card) {
      var item = card.closest(".fx-tree-node-item");
      if (!item) return;
      if (role === "all") {
        item.style.opacity = "";
      } else if (role === "assembly" && card.classList.contains("role-assembly")) {
        item.style.opacity = "";
      } else if (role === "component" && card.classList.contains("role-component")) {
        item.style.opacity = "";
      } else if (role === "replaceable" && (card.classList.contains("role-replaceable_part") || card.classList.contains("role-replaceable"))) {
        item.style.opacity = "";
      } else if (card.classList.contains("role-root")) {
        item.style.opacity = "";
      } else {
        item.style.opacity = "0.3";
      }
    });
  });

  // Live Tree Search Filtering
  document.addEventListener("input", function (e) {
    var input = e.target.closest("[data-tree-search]");
    if (!input) return;
    var query = input.value.trim().toLowerCase();
    var nodeItems = document.querySelectorAll(".fx-tree-node-item");

    if (!query) {
      nodeItems.forEach(function (item) { item.style.display = ""; });
      return;
    }

    nodeItems.forEach(function (item) {
      var card = item.querySelector(":scope > .fx-tree-node-card");
      var text = card ? card.textContent.toLowerCase() : "";
      if (text.indexOf(query) !== -1) {
        item.style.display = "";
        // ensure ancestors are visible
        var parent = item.parentElement.closest(".fx-tree-node-item");
        while (parent) {
          parent.style.display = "";
          var parentBranch = parent.querySelector(":scope > .fx-tree-branch");
          if (parentBranch) parentBranch.style.display = "";
          parent = parent.parentElement.closest(".fx-tree-node-item");
        }
      } else {
        var hasMatchingChild = item.querySelector(".fx-tree-branch .fx-tree-node-item");
        // if children match, keep open
        var childText = item.querySelector(".fx-tree-branch") ? item.querySelector(".fx-tree-branch").textContent.toLowerCase() : "";
        if (childText.indexOf(query) !== -1) {
          item.style.display = "";
        } else {
          item.style.display = "none";
        }
      }
    });
  });

  // Clear Search Button
  document.addEventListener("click", function (e) {
    var clearBtn = e.target.closest(".fx-tree-search-clear");
    if (!clearBtn) return;
    var searchBox = clearBtn.closest(".fx-tree-search");
    if (!searchBox) return;
    var input = searchBox.querySelector("input");
    if (input) {
      input.value = "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
    }
  });

  // Copy Part Number Feedback
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    var text = btn.dataset.copy;
    if (navigator.clipboard && text) {
      navigator.clipboard.writeText(text).then(function () {
        var orig = btn.innerHTML;
        btn.innerHTML = "✓ Copied";
        setTimeout(function () { btn.innerHTML = orig; }, 1500);
      });
    }
  });

  // Global Toast auto-dismiss handler
  function initAutoDismiss() {
    var alerts = document.querySelectorAll(".fx-toast-message:not([data-dismiss-queued]), [data-auto-dismiss]:not([data-dismiss-queued])");
    alerts.forEach(function (el) {
      window.initToastElement(el);
    });
  }

  initAutoDismiss();
  document.body.addEventListener("htmx:afterSettle", initAutoDismiss);
  document.body.addEventListener("htmx:afterSwap", initAutoDismiss);
});


/* Auto-detect user timezone and sync with server session/cookie */
(function () {
  try {
    var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (tz && document.cookie.indexOf('user_timezone=' + tz) === -1) {
      document.cookie = 'user_timezone=' + encodeURIComponent(tz) + '; path=/; max-age=31536000; SameSite=Lax';
    }
  } catch (e) {}
})();


/* Global HTMX Loading Bar & Modal Event Management */
document.body.addEventListener("htmx:configRequest", function () {
  var bar = document.getElementById("global-loading-indicator");
  if (bar) { bar.classList.add("is-active"); }
});

document.body.addEventListener("htmx:afterOnLoad", function () {
  var bar = document.getElementById("global-loading-indicator");
  if (bar) { bar.classList.remove("is-active"); }
});

document.body.addEventListener("htmx:responseError", function (evt) {
  var bar = document.getElementById("global-loading-indicator");
  if (bar) { bar.classList.remove("is-active"); }
  var status = evt.detail && evt.detail.xhr ? evt.detail.xhr.status : 500;
  var msg = "Request failed (" + status + "). Please verify and try again.";
  if (status === 403) msg = "Access Denied: You do not have permission to perform this action.";
  else if (status === 404) msg = "Not Found: The requested record does not exist.";
  else if (status === 400) msg = "Validation Error: Please review required form fields.";
  else if (status >= 500) msg = "Server Error: Unable to complete your request. Please try again shortly.";
  window.fxToast(msg, "danger");
});

document.body.addEventListener("htmx:sendError", function () {
  var bar = document.getElementById("global-loading-indicator");
  if (bar) { bar.classList.remove("is-active"); }
  window.fxToast("Network communication error. Please check your internet connection.", "danger");
});

/* Universal HTMX Modal Controller (Sites, Assets, Checklists, Work Orders) */
document.body.addEventListener("htmx:afterSwap", function (evt) {
  if (evt.detail && evt.detail.target && evt.detail.target.id && evt.detail.target.id.endsWith("ModalContent")) {
    var modalEl = evt.detail.target.closest(".modal");
    if (modalEl && window.bootstrap) {
      var modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.show();
    }
  }
});

["closeSiteModal", "closeAssetModal", "closeChecklistModal", "closeWorkOrderModal"].forEach(function (evtName) {
  document.body.addEventListener(evtName, function () {
    document.querySelectorAll(".modal.show").forEach(function (m) {
      var inst = bootstrap.Modal.getInstance(m);
      if (inst) { inst.hide(); }
    });
    setTimeout(function () {
      document.querySelectorAll(".modal-backdrop").forEach(function (b) { b.remove(); });
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("overflow");
      document.body.style.removeProperty("padding-right");
    }, 200);
  });
});

/* ==========================================================================
   Universal Data-Label Injector for Mobile Responsive Table Cards
   ========================================================================== */
function setupResponsiveTables() {
  document.querySelectorAll("table").forEach(function (table) {
    if (table.classList.contains("wo-list-table")) return;
    var ths = table.querySelectorAll("thead th");
    if (!ths.length) return;
    var labels = Array.from(ths).map(function (th) {
      return th.textContent.trim();
    });
    table.querySelectorAll("tbody tr").forEach(function (tr) {
      var cells = Array.from(tr.children).filter(function (c) {
        return c.tagName.toLowerCase() === "td";
      });
      cells.forEach(function (td, idx) {
        if (!td.getAttribute("data-label") && labels[idx]) {
          td.setAttribute("data-label", labels[idx]);
        }
      });
    });
  });
}

document.addEventListener("DOMContentLoaded", setupResponsiveTables);
document.body.addEventListener("htmx:afterSwap", setupResponsiveTables);
document.body.addEventListener("htmx:afterSettle", setupResponsiveTables);
