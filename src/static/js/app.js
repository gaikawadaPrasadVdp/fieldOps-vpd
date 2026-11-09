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

/* Asset form: choosing another category reloads the form with the typed values so the category's custom attributes
   appear (the server builds and validates those fields) without reloading the host page. */
document.addEventListener("change", function (e) {
  var sel = e.target.closest("select[data-category-reload]");
  if (!sel || !sel.form) return;
  var params = new URLSearchParams();
  new FormData(sel.form).forEach(function (value, key) {
    if (typeof value === "string" && key !== "csrfmiddlewaretoken" && key.indexOf("attr_") !== 0 && value !== "") {
      params.set(key, value);
    }
  });
  var action = sel.form.getAttribute("action") || window.location.pathname;
  var url = action + (action.indexOf("?") === -1 ? "?" : "&") + params.toString();
  if (sel.form.id === "asset-modal-form" && window.htmx && document.getElementById("assetModalContent")) {
    window.htmx.ajax("GET", url, { target: "#assetModalContent", swap: "innerHTML" });
  } else {
    window.location.href = url;
  }
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
  } catch (e) { }
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
    if (typeof filterAssetZonesBySite === "function") {
      filterAssetZonesBySite(evt.detail.target);
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


/* ==========================================================================
   Universal Password Visibility Toggle
   ========================================================================== */
document.addEventListener("click", function (e) {
  var toggleBtn = e.target.closest(".fx-password-toggle");
  if (!toggleBtn) return;
  e.preventDefault();
  e.stopPropagation();

  var targetId = toggleBtn.getAttribute("data-target");
  var input = targetId ? document.getElementById(targetId) : null;
  if (!input) {
    var group = toggleBtn.closest(".input-group");
    if (group) {
      input = group.querySelector("input[type='password'], input[type='text']");
    }
  }
  if (!input) {
    var prev = toggleBtn.previousElementSibling;
    if (prev && prev.tagName && prev.tagName.toLowerCase() === "input") {
      input = prev;
    }
  }
  if (!input) return;

  var isPassword = (input.type === "password");
  input.type = isPassword ? "text" : "password";

  var showIcon = toggleBtn.querySelector(".fx-pw-show");
  var hideIcon = toggleBtn.querySelector(".fx-pw-hide");
  if (showIcon && hideIcon) {
    if (isPassword) {
      showIcon.classList.add("d-none");
      hideIcon.classList.remove("d-none");
      toggleBtn.setAttribute("aria-label", "Hide password");
      toggleBtn.setAttribute("title", "Hide password");
    } else {
      showIcon.classList.remove("d-none");
      hideIcon.classList.add("d-none");
      toggleBtn.setAttribute("aria-label", "Show password");
      toggleBtn.setAttribute("title", "Show password");
    }
  } else {
    var svg = toggleBtn.querySelector("svg");
    if (svg) {
      if (isPassword) {
        svg.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>';
        toggleBtn.setAttribute("aria-label", "Hide password");
        toggleBtn.setAttribute("title", "Hide password");
      } else {
        svg.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
        toggleBtn.setAttribute("aria-label", "Show password");
        toggleBtn.setAttribute("title", "Show password");
      }
    }
  }

  try { input.focus(); } catch (err) { }
});

/* ==========================================================================
   Universal Form Validation & Feedback System
   ========================================================================== */
(function () {
  function getFieldLabel(field) {
    if (!field) return "This field";
    var id = field.id;
    if (id) {
      var labelEl = document.querySelector('label[for="' + id + '"]');
      if (labelEl) {
        var clone = labelEl.cloneNode(true);
        clone.querySelectorAll(".text-danger, .badge, small").forEach(function (el) { el.remove(); });
        var text = clone.textContent.trim().replace(/:$/, "");
        if (text) return text;
      }
    }
    var parent = field.closest(".mb-3, .form-group, .col-md-6, .col-12");
    if (parent) {
      var l = parent.querySelector("label");
      if (l) {
        var c = l.cloneNode(true);
        c.querySelectorAll(".text-danger, .badge, small").forEach(function (el) { el.remove(); });
        var t = c.textContent.trim().replace(/:$/, "");
        if (t) return t;
      }
    }
    return field.placeholder || field.name || "This field";
  }

  function getErrorMessage(field) {
    var label = getFieldLabel(field);
    var validity = field.validity;

    if (validity.valueMissing) {
      if (field.type === "checkbox") return "You must accept this to proceed.";
      if (field.tagName.toLowerCase() === "select") return "Please select an option for " + label + ".";
      return label + " is required.";
    }

    if (validity.typeMismatch) {
      if (field.type === "email") return "Please enter a valid email address (e.g. name@example.com).";
      if (field.type === "url") return "Please enter a valid website URL (starting with http:// or https://).";
    }

    if (field.type === "email" && field.value) {
      var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(field.value.trim())) {
        return "Please enter a valid email address format.";
      }
    }

    if (validity.tooShort) {
      return label + " must be at least " + field.minLength + " characters long (currently " + field.value.length + ").";
    }

    if (validity.tooLong) {
      return label + " must not exceed " + field.maxLength + " characters.";
    }

    if (validity.rangeUnderflow) {
      return "Value must be at least " + field.min + ".";
    }

    if (validity.rangeOverflow) {
      return "Value must not exceed " + field.max + ".";
    }

    if (validity.patternMismatch) {
      return field.title || "Please match the requested format.";
    }

    return field.validationMessage || "Please enter a valid value.";
  }

  function showFieldError(field, message) {
    field.classList.add("is-invalid");
    field.classList.remove("is-valid");

    var container = field.closest(".input-group") || field;
    var parent = container.parentElement;
    if (!parent) return;

    var errEl = parent.querySelector("div.field-error-message, div.invalid-feedback");
    if (!errEl) {
      errEl = document.createElement("div");
      errEl.className = "invalid-feedback text-danger small mt-1 fw-medium field-error-message";
      errEl.setAttribute("data-dynamic-error", "1");
      if (container.nextSibling) {
        parent.insertBefore(errEl, container.nextSibling);
      } else {
        parent.appendChild(errEl);
      }
    }
    errEl.textContent = message;
    errEl.style.display = "block";
    errEl.classList.add("d-block");

    var allErrDivs = parent.querySelectorAll("div.field-error-message, div.invalid-feedback, div.text-danger");
    for (var i = 0; i < allErrDivs.length; i++) {
      if (allErrDivs[i] !== errEl) {
        allErrDivs[i].remove();
      }
    }
  }

  function clearFieldError(field) {
    field.classList.remove("is-invalid");
    var container = field.closest(".input-group") || field;
    var parent = container.parentElement;
    if (parent) {
      var allErrDivs = parent.querySelectorAll("div.field-error-message, div.invalid-feedback, div.text-danger");
      allErrDivs.forEach(function (el) {
        el.textContent = "";
        el.style.display = "none";
        el.classList.remove("d-block");
      });
    }
  }

  function validateField(field) {
    if (field.disabled || field.type === "hidden" || field.type === "submit" || field.type === "button") {
      return true;
    }

    var isValid = field.checkValidity();
    var customMsg = "";

    if (isValid && field.type === "email" && field.value.trim()) {
      var strictEmailRegex = /^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z][a-zA-Z0-9-]*(\.[a-zA-Z][a-zA-Z0-9-]*)*\.[a-zA-Z]{2,}$/;
      if (!strictEmailRegex.test(field.value.trim())) {
        isValid = false;
        customMsg = "Enter a valid email address with a valid domain (e.g. user@gmail.com). Domain names must start with a letter and have a valid extension.";
      }
    }

    if (isValid && field.id === "id_new_password2") {
      var p1 = document.getElementById("id_new_password1");
      if (p1 && p1.value !== field.value) {
        isValid = false;
        customMsg = "The two password fields didn't match.";
      }
    }

    if (isValid && field.id === "id_downtime_started_at" && field.value) {
      var occEl = document.getElementById("id_occurred_at");
      var dtVal = new Date(field.value);
      var now = Date.now();
      var futureLimit = new Date(now + 5 * 60 * 1000);
      var pastLimit = new Date(now - 90 * 24 * 60 * 60 * 1000);

      if (dtVal > futureLimit) {
        isValid = false;
        customMsg = "The downtime start cannot be in the future.";
      } else if (dtVal < pastLimit) {
        isValid = false;
        customMsg = "The downtime start cannot be more than 90 days in the past.";
      } else if (occEl && occEl.value && dtVal < new Date(occEl.value)) {
        isValid = false;
        customMsg = "The downtime start cannot be before the incident occurred.";
      }
    }

    if (isValid && field.id === "id_occurred_at" && field.value) {
      var occVal = new Date(field.value);
      var now = Date.now();
      var futureLimit = new Date(now + 5 * 60 * 1000);
      var pastLimit = new Date(now - 90 * 24 * 60 * 60 * 1000);

      if (occVal > futureLimit) {
        isValid = false;
        customMsg = "The time of the failure cannot be in the future.";
      } else if (occVal < pastLimit) {
        isValid = false;
        customMsg = "The time of the failure cannot be more than 90 days in the past.";
      }
    }

    if (!isValid) {
      var msg = customMsg || getErrorMessage(field);
      showFieldError(field, msg);
      return false;
    } else {
      clearFieldError(field);
      return true;
    }
  }

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form || form.tagName.toLowerCase() !== "form") return;
    if (form.dataset.noValidation === "true") return;

    var fields = Array.from(form.querySelectorAll("input, select, textarea"));
    var firstInvalid = null;
    var allValid = true;

    fields.forEach(function (field) {
      var valid = validateField(field);
      if (!valid) {
        allValid = false;
        if (!firstInvalid) firstInvalid = field;
      }
    });

    if (!allValid) {
      e.preventDefault();
      e.stopPropagation();

      if (firstInvalid) {
        firstInvalid.focus();
        firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
      }

      if (window.fxToast) {
        window.fxToast("Please complete all required fields correctly before submitting.", "warning");
      }
    } else {
      if (form.dataset.submitting === "true") {
        e.preventDefault();
        return;
      }
      form.dataset.submitting = "true";
      setTimeout(function () {
        var submitBtns = form.querySelectorAll("button[type='submit'], input[type='submit']");
        submitBtns.forEach(function (btn) {
          btn.disabled = true;
        });
      }, 50);
    }
  });

  window.addEventListener("pageshow", function () {
    document.querySelectorAll("form").forEach(function (form) {
      delete form.dataset.submitting;
      form.querySelectorAll("button[type='submit'], input[type='submit']").forEach(function (btn) {
        btn.disabled = false;
      });
    });
  });

  document.addEventListener("input", function (e) {
    var field = e.target;
    if (field && field.classList.contains("is-invalid")) {
      validateField(field);
    }
    if (field && (field.id === "id_occurred_at" || field.id === "id_downtime_started_at")) {
      var dtEl = document.getElementById("id_downtime_started_at");
      if (dtEl && dtEl.value) {
        validateField(dtEl);
      }
      var occEl = document.getElementById("id_occurred_at");
      if (occEl && occEl.value) {
        validateField(occEl);
      }
    }
  });

  document.addEventListener("change", function (e) {
    var field = e.target;
    if (field && (field.tagName.toLowerCase() === "select" || field.type === "checkbox" || field.type === "radio" || field.type === "datetime-local" || field.type === "date")) {
      validateField(field);
    }
    if (field && (field.id === "id_occurred_at" || field.id === "id_downtime_started_at")) {
      var dtEl = document.getElementById("id_downtime_started_at");
      if (dtEl && dtEl.value) {
        validateField(dtEl);
      }
      var occEl = document.getElementById("id_occurred_at");
      if (occEl && occEl.value) {
        validateField(occEl);
      }
    }
  });

})();

/* ==========================================================================
   Site Form Dynamic Geo-Cascading & Real-Time Validation
   ========================================================================== */
(function () {
  var geoStates = {
    "IN": [
      "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
      "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
      "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
      "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
      "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
      "Uttar Pradesh", "Uttarakhand", "West Bengal",
      "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
      "Delhi (NCT)", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
    ],
    "US": [
      "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
      "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
      "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
      "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
      "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
      "New Hampshire", "New Jersey", "New Mexico", "New York",
      "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
      "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
      "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
      "West Virginia", "Wisconsin", "Wyoming", "District of Columbia"
    ],
    "GB": ["England", "Scotland", "Wales", "Northern Ireland"],
    "AE": ["Abu Dhabi", "Dubai", "Sharjah", "Ajman", "Ras Al Khaimah", "Fujairah", "Umm Al-Quwain"],
    "CA": ["Alberta", "British Columbia", "Manitoba", "New Brunswick", "Newfoundland and Labrador", "Nova Scotia", "Ontario", "Prince Edward Island", "Quebec", "Saskatchewan"],
    "AU": ["New South Wales", "Victoria", "Queensland", "Western Australia", "South Australia", "Tasmania", "Australian Capital Territory", "Northern Territory"],
    "DE": ["Baden-Württemberg", "Bavaria", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hesse", "Lower Saxony", "Mecklenburg-Vorpommern", "North Rhine-Westphalia", "Rhineland-Palatinate", "Saarland", "Saxony", "Saxony-Anhalt", "Schleswig-Holstein", "Thuringia"],
    "FR": ["Île-de-France", "Auvergne-Rhône-Alpes", "Nouvelle-Aquitaine", "Occitanie", "Hauts-de-France", "Provence-Alpes-Côte d'Azur", "Grand Est", "Pays de la Loire", "Normandy", "Brittany"],
    "SG": ["Central", "East", "North", "North-East", "West"]
  };

  var geoCities = {
    "Kerala": ["Kochi", "Thiruvananthapuram", "Kozhikode", "Thrissur", "Kollam", "Kannur", "Alappuzha", "Palakkad", "Kottayam", "Malappuram", "Kasaragod", "Pathanamthitta", "Idukki", "Wayanad"],
    "Karnataka": ["Bengaluru", "Mysuru", "Hubballi-Dharwad", "Mangaluru", "Belagavi", "Kalaburagi", "Ballari", "Davanagere", "Shivamogga", "Tumakuru", "Udupi", "Bidar", "Hosapete"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Kalyan-Dombivli", "Vasai-Virar", "Aurangabad", "Navi Mumbai", "Solapur", "Kolhapur", "Amravati", "Nanded"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tiruppur", "Erode", "Tirunelveli", "Vellore", "Thoothukudi", "Dindigul", "Thanjavur"],
    "Delhi": ["New Delhi", "Central Delhi", "North Delhi", "South Delhi", "East Delhi", "West Delhi", "Dwarka", "Rohini", "Connaught Place"],
    "Delhi (NCT)": ["New Delhi", "Central Delhi", "North Delhi", "South Delhi", "East Delhi", "West Delhi", "Dwarka", "Rohini", "Connaught Place"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Ramagundam", "Khammam", "Mahbubnagar", "Nalgonda"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar", "Gandhinagar", "Junagadh", "Anand", "Navsari", "Morbi"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri", "Bardhaman", "Malda", "Kharagpur", "Haldia"],
    "Uttar Pradesh": ["Noida", "Greater Noida", "Lucknow", "Kanpur", "Ghaziabad", "Agra", "Varanasi", "Meerut", "Prayagraj", "Bareilly", "Aligarh", "Moradabad", "Gorakhpur"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool", "Kakinada", "Rajahmundry", "Tirupati", "Kadapa", "Anantapur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur", "Bhilwara", "Alwar", "Bharatpur", "Sikar"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat", "Ambala", "Yamunanagar", "Rohtak", "Hisar", "Karnal", "Sonipat", "Panchkula"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda", "Mohali", "Hoshiarpur", "Pathankot"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain", "Sagar", "Dewas", "Satna", "Ratlam"],
    "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia", "Darbhanga", "Bihar Sharif", "Arrah", "Begusarai"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur", "Puri", "Balasore", "Bhadrak"],
    "Assam": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia", "Tezpur"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro Steel City", "Deoghar", "Hazaribagh"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Roorkee", "Haldwani", "Rishikesh", "Nainital"],
    "Himachal Pradesh": ["Shimla", "Dharamshala", "Solan", "Mandi", "Baddi", "Kullu"],
    "Chandigarh": ["Chandigarh"],
    "Jammu and Kashmir": ["Srinagar", "Jammu", "Anantnag", "Baramulla"],
    "Ladakh": ["Leh", "Kargil"],
    "Puducherry": ["Puducherry", "Karaikal", "Oulgaret"],
    "California": ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento", "Fresno"],
    "Texas": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso"],
    "New York": ["New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse", "Albany"],
    "Florida": ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale"],
    "Illinois": ["Chicago", "Aurora", "Naperville", "Joliet", "Rockford"],
    "Washington": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue"],
    "Dubai": ["Dubai", "Jebel Ali", "Deira", "Bur Dubai", "Business Bay"],
    "Abu Dhabi": ["Abu Dhabi", "Al Ain", "Al Dhafra", "Mussafah"],
    "England": ["London", "Manchester", "Birmingham", "Leeds", "Liverpool", "Bristol"],
    "Scotland": ["Edinburgh", "Glasgow", "Aberdeen", "Dundee"],
    "Ontario": ["Toronto", "Ottawa", "Mississauga", "Brampton", "Hamilton"],
    "Quebec": ["Montreal", "Quebec City", "Laval", "Gatineau"],
    "New South Wales": ["Sydney", "Newcastle", "Central Coast", "Wollongong"],
    "Victoria": ["Melbourne", "Geelong", "Ballarat", "Bendigo"],
    "Bavaria": ["Munich", "Nuremberg", "Augsburg", "Regensburg"],
    "Berlin": ["Berlin"]
  };

  var indiaStatePin = {
    "Delhi": { prefixes: ["11"], sample: "110001" },
    "Delhi (NCT)": { prefixes: ["11"], sample: "110001" },
    "Haryana": { prefixes: ["12", "13"], sample: "122001" },
    "Punjab": { prefixes: ["14", "15"], sample: "141001" },
    "Chandigarh": { prefixes: ["16"], sample: "160017" },
    "Himachal Pradesh": { prefixes: ["17"], sample: "171001" },
    "Jammu and Kashmir": { prefixes: ["18", "19"], sample: "190001" },
    "Ladakh": { prefixes: ["19"], sample: "194101" },
    "Uttar Pradesh": { prefixes: ["20", "21", "22", "23", "24", "25", "26", "27", "28"], sample: "201301" },
    "Uttarakhand": { prefixes: ["24", "26"], sample: "248001" },
    "Rajasthan": { prefixes: ["30", "31", "32", "33", "34"], sample: "302001" },
    "Gujarat": { prefixes: ["36", "37", "38", "39"], sample: "380001" },
    "Dadra and Nagar Haveli and Daman and Diu": { prefixes: ["39"], sample: "396210" },
    "Maharashtra": { prefixes: ["40", "41", "42", "43", "44"], sample: "400001" },
    "Goa": { prefixes: ["40"], sample: "403001" },
    "Madhya Pradesh": { prefixes: ["45", "46", "47", "48"], sample: "452001" },
    "Chhattisgarh": { prefixes: ["49"], sample: "492001" },
    "Telangana": { prefixes: ["50"], sample: "500001" },
    "Andhra Pradesh": { prefixes: ["51", "52", "53"], sample: "530001" },
    "Karnataka": { prefixes: ["56", "57", "58", "59"], sample: "560001" },
    "Tamil Nadu": { prefixes: ["60", "61", "62", "63", "64"], sample: "600001" },
    "Puducherry": { prefixes: ["60"], sample: "605001" },
    "Kerala": { prefixes: ["67", "68", "69"], sample: "682001" },
    "Lakshadweep": { prefixes: ["68"], sample: "682555" },
    "West Bengal": { prefixes: ["70", "71", "72", "73", "74"], sample: "700001" },
    "Andaman and Nicobar Islands": { prefixes: ["74"], sample: "744101" },
    "Sikkim": { prefixes: ["73"], sample: "737101" },
    "Odisha": { prefixes: ["75", "76", "77"], sample: "751001" },
    "Assam": { prefixes: ["78"], sample: "781001" },
    "Arunachal Pradesh": { prefixes: ["79"], sample: "791111" },
    "Manipur": { prefixes: ["79"], sample: "795001" },
    "Meghalaya": { prefixes: ["79"], sample: "793001" },
    "Mizoram": { prefixes: ["79"], sample: "796001" },
    "Nagaland": { prefixes: ["79"], sample: "797001" },
    "Tripura": { prefixes: ["79"], sample: "799001" },
    "Bihar": { prefixes: ["80", "81", "82", "83", "84", "85"], sample: "800001" },
    "Jharkhand": { prefixes: ["81", "82", "83"], sample: "834001" }
  };

  var cityPincodes = {
    "Bengaluru": "560001", "Mysuru": "570001", "Hubballi-Dharwad": "580001", "Mangaluru": "575001", "Belagavi": "590001",
    "Mumbai": "400001", "Pune": "411001", "Nagpur": "440001", "Thane": "400601", "Nashik": "422001",
    "Chennai": "600001", "Coimbatore": "641001", "Madurai": "625001", "Salem": "636001",
    "New Delhi": "110001", "Central Delhi": "110001", "North Delhi": "110007", "South Delhi": "110017", "Dwarka": "110075",
    "Hyderabad": "500001", "Warangal": "506001", "Visakhapatnam": "530001", "Vijayawada": "520001",
    "Ahmedabad": "380001", "Surat": "395001", "Vadodara": "390001",
    "Kolkata": "700001", "Howrah": "711101", "Durgapur": "713201",
    "Noida": "201301", "Greater Noida": "201310", "Lucknow": "226001", "Kanpur": "208001",
    "Gurugram": "122001", "Faridabad": "121001", "Jaipur": "302001",
    "Kochi": "682001", "Thiruvananthapuram": "695001", "Kozhikode": "673001", "Thrissur": "680001",
    "Chandigarh": "160017", "Indore": "452001", "Patna": "800001", "Bhubaneswar": "751001",
    "Guwahati": "781001", "Panaji": "403001", "Dehradun": "248001", "Shimla": "171001"
  };

  var geoTimezones = {
    "IN": "Asia/Kolkata", "US": "America/New_York", "GB": "Europe/London",
    "AE": "Asia/Dubai", "SG": "Asia/Singapore", "AU": "Australia/Sydney",
    "CA": "America/Toronto", "DE": "Europe/Berlin", "FR": "Europe/Paris"
  };

  var geoPrefixes = {
    "IN": "+91", "US": "+1", "GB": "+44", "AE": "+971", "SG": "+65",
    "AU": "+61", "CA": "+1", "DE": "+49", "FR": "+33"
  };

  function setFieldError(field, msg) {
    if (!field) return;
    field.classList.add("is-invalid");
    var parent = field.closest(".mb-3") || field.parentElement;
    var errEl = parent.querySelector(".field-error-message, .invalid-feedback, .js-field-error");
    if (!errEl) {
      errEl = document.createElement("div");
      errEl.className = "invalid-feedback d-block text-danger small mt-1 fw-medium field-error-message";
      var helpText = parent.querySelector(".form-text");
      if (helpText) {
        parent.insertBefore(errEl, helpText);
      } else {
        parent.appendChild(errEl);
      }
    }
    errEl.className = "invalid-feedback d-block text-danger small mt-1 fw-medium field-error-message";
    errEl.textContent = msg;
    errEl.style.display = "block";
  }

  function clearFieldError(field) {
    if (!field) return;
    field.classList.remove("is-invalid");
    var parent = field.closest(".mb-3") || field.parentElement;
    var errEls = parent.querySelectorAll(".field-error-message, .invalid-feedback, .js-field-error");
    errEls.forEach(function (errEl) {
      errEl.textContent = "";
      errEl.style.display = "none";
    });
  }

  function initSiteForm(root) {
    var form = (root && root.id === "site-modal-form") ? root : (root ? root.querySelector("#site-modal-form") : null);
    if (!form || form.dataset.siteValidationInitialized === "true") return;
    form.dataset.siteValidationInitialized = "true";

    var countryEl = form.querySelector("#id_country");
    var stateEl = form.querySelector("#id_state_region");
    var cityEl = form.querySelector("#id_city");
    var tzEl = form.querySelector("#id_timezone");
    var phoneEl = form.querySelector("#id_contact_phone");
    var postalEl = form.querySelector("#id_postal_code");
    var codeEl = form.querySelector("input[name='code']");
    var nameEl = form.querySelector("input[name='name']");

    if (!countryEl || !stateEl || !cityEl) return;

    // Code input auto-uppercase
    if (codeEl) {
      codeEl.addEventListener("input", function () {
        var start = this.selectionStart;
        var end = this.selectionEnd;
        this.value = this.value.toUpperCase();
        this.setSelectionRange(start, end);
        if (this.value.trim()) clearFieldError(this);
      });
    }

    function validateNameField() {
      if (!nameEl) return true;
      var name = (nameEl.value || "").trim();
      if (!name) {
        setFieldError(nameEl, "Site name is required.");
        return false;
      }
      if (name.length < 2) {
        setFieldError(nameEl, "Site name must be at least 2 characters.");
        return false;
      }
      if (/\d/.test(name)) {
        setFieldError(nameEl, "Site name must contain only alphabetical characters and cannot contain numbers.");
        return false;
      }
      if (!/^[a-zA-Z\s'-]+$/.test(name)) {
        setFieldError(nameEl, "Site name must contain only alphabetical characters.");
        return false;
      }
      clearFieldError(nameEl);
      return true;
    }

    if (nameEl) {
      nameEl.addEventListener("input", function () {
        var name = this.value;
        if (/\d/.test(name)) {
          setFieldError(this, "Site name must contain only alphabetical characters and cannot contain numbers.");
        } else if (!/^[a-zA-Z\s'-]*$/.test(name)) {
          setFieldError(this, "Site name must contain only alphabetical characters.");
        } else if (name.trim().length >= 2) {
          clearFieldError(this);
        }
      });
      nameEl.addEventListener("blur", function () {
        validateNameField();
      });
    }

    var contactNameEl = form.querySelector("input[name='contact_name']");
    function validateContactNameField() {
      if (!contactNameEl) return true;
      var cname = (contactNameEl.value || "").trim();
      if (cname) {
        if (cname.length < 2) {
          setFieldError(contactNameEl, "Contact name must be at least 2 characters.");
          return false;
        }
        if (/\d/.test(cname)) {
          setFieldError(contactNameEl, "Contact name must contain only alphabetical characters and cannot contain numbers.");
          return false;
        }
        if (!/^[a-zA-Z\s'-]+$/.test(cname)) {
          setFieldError(contactNameEl, "Contact name must contain only alphabetical characters.");
          return false;
        }
      }
      clearFieldError(contactNameEl);
      return true;
    }

    if (contactNameEl) {
      contactNameEl.addEventListener("input", function () {
        var cname = this.value;
        if (/\d/.test(cname)) {
          setFieldError(this, "Contact name must contain only alphabetical characters and cannot contain numbers.");
        } else if (!/^[a-zA-Z\s'-]*$/.test(cname)) {
          setFieldError(this, "Contact name must contain only alphabetical characters.");
        } else {
          clearFieldError(this);
        }
      });
      contactNameEl.addEventListener("blur", function () {
        validateContactNameField();
      });
    }

    function validatePhoneField() {
      if (!phoneEl) return true;
      var phone = (phoneEl.value || "").trim();
      if (phone) {
        if (/[a-zA-Z]/.test(phone)) {
          setFieldError(phoneEl, "Phone number cannot contain letters.");
          return false;
        }
        var digits = phone.replace(/\D/g, "");
        if (digits.length < 7) {
          setFieldError(phoneEl, "Phone number must contain at least 7 digits.");
          return false;
        }
        if (digits.length > 15) {
          setFieldError(phoneEl, "Phone number cannot exceed 15 digits.");
          return false;
        }
      }
      clearFieldError(phoneEl);
      return true;
    }

    if (phoneEl) {
      phoneEl.addEventListener("input", function () {
        var phone = this.value;
        if (/[a-zA-Z]/.test(phone)) {
          setFieldError(this, "Phone number cannot contain letters.");
        } else {
          clearFieldError(this);
        }
      });
      phoneEl.addEventListener("blur", function () {
        validatePhoneField();
      });
    }

    function updateStates(country, selectedState) {
      var states = geoStates[country] || [];
      var currentVal = selectedState || stateEl.value;
      stateEl.innerHTML = "";

      var defaultOpt = document.createElement("option");
      defaultOpt.value = "";
      defaultOpt.textContent = "Select State / Region...";
      stateEl.appendChild(defaultOpt);

      var matched = false;
      states.forEach(function (s) {
        var opt = document.createElement("option");
        opt.value = s;
        opt.textContent = s;
        if (s === currentVal) {
          opt.selected = true;
          matched = true;
        }
        stateEl.appendChild(opt);
      });

      if (currentVal && !matched) {
        var customOpt = document.createElement("option");
        customOpt.value = currentVal;
        customOpt.textContent = currentVal;
        customOpt.selected = true;
        stateEl.appendChild(customOpt);
      }
    }

    function updateCities(state, selectedCity) {
      var cities = geoCities[state] || [];
      var currentVal = selectedCity || cityEl.value;
      cityEl.innerHTML = "";

      var defaultOpt = document.createElement("option");
      defaultOpt.value = "";
      defaultOpt.textContent = "Select City...";
      cityEl.appendChild(defaultOpt);

      var matched = false;
      cities.forEach(function (c) {
        var opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        if (c === currentVal) {
          opt.selected = true;
          matched = true;
        }
        cityEl.appendChild(opt);
      });

      if (currentVal && !matched) {
        var customOpt = document.createElement("option");
        customOpt.value = currentVal;
        customOpt.textContent = currentVal;
        customOpt.selected = true;
        cityEl.appendChild(customOpt);
      }
    }

    function getFieldWrapper(el) {
      if (!el) return null;
      if (el.id === "id_country") return form.querySelector("#field-wrapper-country") || el.closest(".col-md-6");
      if (el.id === "id_state_region") return form.querySelector("#field-wrapper-state") || el.closest(".col-md-6");
      if (el.id === "id_city") return form.querySelector("#field-wrapper-city") || el.closest(".col-md-6");
      return el.closest(".col-md-6");
    }

    function updateHierarchyVisibility() {
      var countryVal = (countryEl.value || "").trim().toUpperCase();
      var stateVal = (stateEl.value || "").trim();

      var stateWrapper = getFieldWrapper(stateEl);
      var cityWrapper = getFieldWrapper(cityEl);

      if (stateWrapper) {
        if (countryVal) {
          stateWrapper.classList.remove("d-none");
          stateWrapper.style.display = "";
        } else {
          stateWrapper.classList.add("d-none");
          stateWrapper.style.display = "none";
        }
      }

      if (cityWrapper) {
        if (countryVal && stateVal) {
          cityWrapper.classList.remove("d-none");
          cityWrapper.style.display = "";
        } else {
          cityWrapper.classList.add("d-none");
          cityWrapper.style.display = "none";
        }
      }
    }

    function onCountryChange(isInitial) {
      var country = (countryEl.value || "").trim().toUpperCase();
      var currentState = isInitial ? stateEl.value : "";
      var currentCity = isInitial ? cityEl.value : "";

      updateStates(country, currentState);
      if (!country) {
        stateEl.value = "";
      }

      var stateVal = (stateEl.value || currentState || "").trim();
      updateCities(stateVal, currentCity);
      if (!stateVal) {
        cityEl.value = "";
      }

      updateHierarchyVisibility();

      if (!isInitial && geoTimezones[country] && tzEl) {
        tzEl.value = geoTimezones[country];
        clearFieldError(tzEl);
      }

      if (phoneEl) {
        var prefix = geoPrefixes[country] || "+1";
        phoneEl.placeholder = "e.g. " + prefix + " 98765 43210";
      }

      if (postalEl) {
        if (country === "IN") {
          postalEl.placeholder = "e.g. 560001 (6-digit PIN code)";
        } else if (country === "US") {
          postalEl.placeholder = "e.g. 90210 (5-digit ZIP code)";
        } else {
          postalEl.placeholder = "Postal / ZIP code";
        }
      }
    }

    countryEl.addEventListener("change", function () {
      clearFieldError(this);
      onCountryChange(false);
    });

    stateEl.addEventListener("change", function () {
      clearFieldError(this);
      var state = (this.value || "").trim();
      updateCities(state, "");
      cityEl.value = "";
      clearFieldError(cityEl);
      updateHierarchyVisibility();

      // Update PIN code placeholder based on state's postal circle
      if (countryEl.value === "IN" && postalEl) {
        var info = indiaStatePin[state];
        if (info) {
          postalEl.placeholder = "e.g. " + info.sample + " (" + info.prefixes.join(", ") + "xxxx)";
        }
        if (postalEl.value.trim().length === 6) {
          validatePincode(false);
        }
      }
    });

    cityEl.addEventListener("change", function () {
      clearFieldError(this);
      var city = this.value;
      if (!city) return;

      // Auto-suggest or set related PIN code if empty
      if (cityPincodes[city] && postalEl && !postalEl.value.trim()) {
        postalEl.value = cityPincodes[city];
        clearFieldError(postalEl);
      }
    });

    if (postalEl) {
      postalEl.addEventListener("input", function () {
        var val = this.value.trim();
        var country = (countryEl.value || "").toUpperCase();
        if (country === "IN") {
          this.value = val.replace(/\D/g, "").substring(0, 6);
          val = this.value;
          if (val.length === 6) {
            validatePincode(false);
          } else if (val.length > 0 && val.startsWith("0")) {
            setFieldError(this, "Indian PIN code cannot start with 0.");
          } else {
            clearFieldError(this);
          }
        } else {
          if (val) clearFieldError(this);
        }
      });

      postalEl.addEventListener("blur", function () {
        validatePincode(true);
      });
    }

    function validatePincode(showEmptyError) {
      if (!postalEl) return true;
      var postal = (postalEl.value || "").trim();
      var country = (countryEl.value || "").toUpperCase();

      if (!postal) {
        if (showEmptyError) {
          setFieldError(postalEl, "Postal / PIN code is required.");
          return false;
        }
        return true;
      }

      if (country === "IN") {
        if (!/^[1-9][0-9]{5}$/.test(postal)) {
          setFieldError(postalEl, "PIN code must be exactly 6 digits starting with 1-9 (e.g. 560001).");
          return false;
        }
        var state = stateEl.value;
        var info = indiaStatePin[state];
        if (info) {
          var prefix = postal.substring(0, 2);
          if (info.prefixes.indexOf(prefix) === -1) {
            var validList = info.prefixes.join(", ");
            setFieldError(postalEl, "PIN code " + postal + " does not match " + state + ". Must start with " + validList + " (e.g. " + info.sample + ").");
            return false;
          }
        }
      } else if (country === "US") {
        if (!/^\d{5}(-\d{4})?$/.test(postal)) {
          setFieldError(postalEl, "US ZIP code must be 5 digits (e.g. 90210).");
          return false;
        }
      }

      clearFieldError(postalEl);
      return true;
    }

    // Strict Form Validation on Submit
    form.addEventListener("submit", function (e) {
      var isValid = true;
      var firstInvalid = null;

      // Validate Code
      if (codeEl) {
        var code = (codeEl.value || "").trim();
        if (!code) {
          setFieldError(codeEl, "Site code is required.");
          isValid = false;
          firstInvalid = firstInvalid || codeEl;
        } else if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,29}$/.test(code)) {
          setFieldError(codeEl, "Start with letter/digit. Allowed: uppercase letters, numbers, ., _, -");
          isValid = false;
          firstInvalid = firstInvalid || codeEl;
        } else {
          clearFieldError(codeEl);
        }
      }

      // Validate Name
      if (nameEl) {
        if (!validateNameField()) {
          isValid = false;
          firstInvalid = firstInvalid || nameEl;
        }
      }

      // Validate Contact Name
      if (contactNameEl) {
        if (!validateContactNameField()) {
          isValid = false;
          firstInvalid = firstInvalid || contactNameEl;
        }
      }

      // Validate Contact Phone
      if (phoneEl) {
        if (!validatePhoneField()) {
          isValid = false;
          firstInvalid = firstInvalid || phoneEl;
        }
      }

      // Validate Country
      if (!countryEl.value) {
        setFieldError(countryEl, "Please select a Country.");
        isValid = false;
        firstInvalid = firstInvalid || countryEl;
      } else {
        clearFieldError(countryEl);
      }

      // Validate Timezone
      if (tzEl && !tzEl.value) {
        setFieldError(tzEl, "Please select a Timezone.");
        isValid = false;
        firstInvalid = firstInvalid || tzEl;
      } else if (tzEl) {
        clearFieldError(tzEl);
      }

      // Validate State
      if (!stateEl.value) {
        setFieldError(stateEl, "Please select a State / Region.");
        isValid = false;
        firstInvalid = firstInvalid || stateEl;
      } else {
        clearFieldError(stateEl);
      }

      // Validate City
      if (!cityEl.value) {
        setFieldError(cityEl, "Please select a City.");
        isValid = false;
        firstInvalid = firstInvalid || cityEl;
      } else {
        clearFieldError(cityEl);
      }

      // Validate PIN code
      if (!validatePincode(true)) {
        isValid = false;
        firstInvalid = firstInvalid || postalEl;
      }

      if (!isValid) {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (firstInvalid) {
          firstInvalid.focus();
          firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        return false;
      }
    });

    // Initial setup on render
    var initialState = stateEl.value;
    var initialCity = cityEl.value;
    onCountryChange(true);
    if (initialState) {
      stateEl.value = initialState;
      updateCities(initialState, initialCity);
    }
    updateHierarchyVisibility();
  }

  function initAssetForm(root) {
    var form = (root && (root.id === "asset-modal-form" || root.id === "asset-form"))
      ? root
      : (root ? root.querySelector("#asset-modal-form, #asset-form") : null);
    if (!form || form.dataset.assetValidationInitialized === "true") return;
    form.dataset.assetValidationInitialized = "true";

    var nameEl = form.querySelector("input[name='name']");
    var tagEl = form.querySelector("input[name='asset_tag']");
    var catEl = form.querySelector("select[name='category']");
    var siteEl = form.querySelector("select[name='site']");
    var descEl = form.querySelector("textarea[name='description']");
    var reasonEl = form.querySelector("input[name='reason'], textarea[name='reason']");
    var purchaseEl = form.querySelector("input[name='purchase_date']");
    var commEl = form.querySelector("input[name='commission_date']");

    function validateName() {
      if (!nameEl) return true;
      var val = (nameEl.value || "").trim();
      if (!val) {
        setFieldError(nameEl, "Asset name is required.");
        return false;
      }
      if (val.length < 2) {
        setFieldError(nameEl, "Asset name must be at least 2 characters.");
        return false;
      }
      if (/\d/.test(val)) {
        setFieldError(nameEl, "Asset name must contain only alphabetical characters and cannot contain numbers.");
        return false;
      }
      if (!/^[a-zA-Z\s'-]+$/.test(val)) {
        setFieldError(nameEl, "Asset name must contain only alphabetical characters.");
        return false;
      }
      clearFieldError(nameEl);
      return true;
    }

    if (nameEl) {
      nameEl.addEventListener("input", function () {
        var val = this.value;
        if (/\d/.test(val)) {
          setFieldError(this, "Asset name must contain only alphabetical characters and cannot contain numbers.");
        } else if (!/^[a-zA-Z\s'-]*$/.test(val)) {
          setFieldError(this, "Asset name must contain only alphabetical characters.");
        } else if (val.trim().length >= 2) {
          clearFieldError(this);
        }
      });
      nameEl.addEventListener("blur", validateName);
    }

    function validateTag() {
      if (!tagEl) return true;
      var val = (tagEl.value || "").trim();
      if (!val) {
        setFieldError(tagEl, "Asset tag is required.");
        return false;
      }
      if (!/^[A-Za-z0-9][A-Za-z0-9._\/-]{0,39}$/.test(val)) {
        setFieldError(tagEl, "Asset tag must be 1-40 characters: letters, digits, '.', '_', '/' or '-'.");
        return false;
      }
      clearFieldError(tagEl);
      return true;
    }

    if (tagEl) {
      tagEl.addEventListener("input", function () {
        var val = this.value.trim();
        if (val && !/^[A-Za-z0-9][A-Za-z0-9._\/-]{0,39}$/.test(val)) {
          setFieldError(this, "Asset tag must be 1-40 characters: letters, digits, '.', '_', '/' or '-'.");
        } else if (val) {
          clearFieldError(this);
        }
      });
      tagEl.addEventListener("blur", validateTag);
    }

    function validateDates() {
      if (purchaseEl && commEl && purchaseEl.value && commEl.value) {
        if (new Date(commEl.value) < new Date(purchaseEl.value)) {
          setFieldError(commEl, "Commissioning date cannot be before the purchase date.");
          return false;
        } else {
          clearFieldError(commEl);
        }
      }
      return true;
    }

    if (purchaseEl && commEl) {
      purchaseEl.addEventListener("change", validateDates);
      commEl.addEventListener("change", validateDates);
    }

    if (descEl) {
      descEl.addEventListener("input", function () {
        if (/\d/.test(this.value)) {
          setFieldError(this, "Description must contain only alphabetical characters and cannot contain numbers.");
        } else {
          clearFieldError(this);
        }
      });
      descEl.addEventListener("blur", function () {
        if (this.value && /\d/.test(this.value)) {
          setFieldError(this, "Description must contain only alphabetical characters and cannot contain numbers.");
        } else {
          clearFieldError(this);
        }
      });
    }

    if (reasonEl) {
      reasonEl.addEventListener("input", function () {
        if (/\d/.test(this.value)) {
          setFieldError(this, "Reason must contain only alphabetical characters and cannot contain numbers.");
        } else {
          clearFieldError(this);
        }
      });
      reasonEl.addEventListener("blur", function () {
        if (this.value && /\d/.test(this.value)) {
          setFieldError(this, "Reason must contain only alphabetical characters and cannot contain numbers.");
        } else {
          clearFieldError(this);
        }
      });
    }

    if (catEl) {
      catEl.addEventListener("change", function () {
        if (this.value) clearFieldError(this);
      });
    }

    if (siteEl) {
      siteEl.addEventListener("change", function () {
        if (this.value) clearFieldError(this);
      });
    }

    form.addEventListener("submit", function (e) {
      var valid = true;
      if (!validateTag()) valid = false;
      if (!validateName()) valid = false;
      if (catEl && !catEl.value) {
        setFieldError(catEl, "Category is required.");
        valid = false;
      }
      if (siteEl && !siteEl.value) {
        setFieldError(siteEl, "Site is required.");
        valid = false;
      }
      if (!validateDates()) valid = false;
      if (descEl && descEl.value && /\d/.test(descEl.value)) {
        setFieldError(descEl, "Description must contain only alphabetical characters and cannot contain numbers.");
        valid = false;
      }
      if (reasonEl && reasonEl.value && /\d/.test(reasonEl.value)) {
        setFieldError(reasonEl, "Reason must contain only alphabetical characters and cannot contain numbers.");
        valid = false;
      }

      if (!valid) {
        e.preventDefault();
        e.stopImmediatePropagation();
        var firstErr = form.querySelector(".is-invalid");
        if (firstErr) {
          firstErr.focus();
          firstErr.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        if (window.fxToast) {
          window.fxToast("Please complete all required fields correctly before submitting.", "warning");
        }
      }
    });
  }

  function initMemberInviteForm(root) {
    var form = (root && root.id === "member-invite-form")
      ? root
      : (root ? root.querySelector("#member-invite-form") : null);
    if (!form || form.dataset.inviteValidationInitialized === "true") return;
    form.dataset.inviteValidationInitialized = "true";

    var emailEl = form.querySelector("input[name='email'], input[type='email']");
    var nameEl = form.querySelector("input[name='full_name']");
    var pwdEl = form.querySelector("input[name='password']");
    var rolesEls = form.querySelectorAll("input[name='roles']");

    var strictEmailRegex = /^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z][a-zA-Z0-9-]*(\.[a-zA-Z][a-zA-Z0-9-]*)*\.[a-zA-Z]{2,}$/;

    function validateEmail() {
      if (!emailEl) return true;
      var val = (emailEl.value || "").trim();
      if (!val) {
        setFieldError(emailEl, "Email is required.");
        return false;
      }
      if (!strictEmailRegex.test(val)) {
        setFieldError(emailEl, "Enter a valid email address with a valid domain (e.g. user@gmail.com). Domain names must start with a letter and have a valid extension.");
        return false;
      }
      clearFieldError(emailEl);
      return true;
    }

    if (emailEl) {
      emailEl.addEventListener("input", function () {
        var val = this.value.trim();
        if (val && !strictEmailRegex.test(val)) {
          setFieldError(this, "Enter a valid email address with a valid domain (e.g. user@gmail.com). Domain names must start with a letter and have a valid extension.");
        } else if (val) {
          clearFieldError(this);
        }
      });
      emailEl.addEventListener("blur", validateEmail);
    }

    function validateFullName() {
      if (!nameEl) return true;
      var val = (nameEl.value || "").trim();
      if (!val) {
        setFieldError(nameEl, "Full name is required.");
        return false;
      }
      if (val.length < 2) {
        setFieldError(nameEl, "Full name must be at least 2 characters.");
        return false;
      }
      if (/\d/.test(val)) {
        setFieldError(nameEl, "Full name must contain only alphabetical characters and cannot contain numbers.");
        return false;
      }
      if (!/^[a-zA-Z\s'-]+$/.test(val)) {
        setFieldError(nameEl, "Full name must contain only alphabetical characters.");
        return false;
      }
      clearFieldError(nameEl);
      return true;
    }

    if (nameEl) {
      nameEl.addEventListener("input", function () {
        var val = this.value;
        if (/\d/.test(val)) {
          setFieldError(this, "Full name must contain only alphabetical characters and cannot contain numbers.");
        } else if (!/^[a-zA-Z\s'-]*$/.test(val)) {
          setFieldError(this, "Full name must contain only alphabetical characters.");
        } else if (val.trim().length >= 2) {
          clearFieldError(this);
        }
      });
      nameEl.addEventListener("blur", validateFullName);
    }

    function validatePassword() {
      if (!pwdEl) return true;
      var val = (pwdEl.value || "").trim();
      if (!val) {
        setFieldError(pwdEl, "Password is required.");
        return false;
      }
      if (val.length < 8) {
        setFieldError(pwdEl, "Password must be at least 8 characters.");
        return false;
      }
      clearFieldError(pwdEl);
      return true;
    }

    if (pwdEl) {
      pwdEl.addEventListener("input", function () {
        var val = this.value;
        if (val && val.length < 8) {
          setFieldError(this, "Password must be at least 8 characters.");
        } else {
          clearFieldError(this);
        }
      });
      pwdEl.addEventListener("blur", validatePassword);
    }

    function validateRoles() {
      if (!rolesEls || rolesEls.length === 0) return true;
      var anyChecked = Array.from(rolesEls).some(function (r) { return r.checked; });
      if (!anyChecked) {
        setFieldError(rolesEls[0], "Please select at least one role.");
        return false;
      }
      clearFieldError(rolesEls[0]);
      return true;
    }

    rolesEls.forEach(function (r) {
      r.addEventListener("change", function () {
        validateRoles();
      });
    });

    form.addEventListener("submit", function (e) {
      var valid = true;
      if (!validateEmail()) valid = false;
      if (!validateFullName()) valid = false;
      if (!validatePassword()) valid = false;
      if (!validateRoles()) valid = false;

      if (!valid) {
        e.preventDefault();
        e.stopImmediatePropagation();
        var firstErr = form.querySelector(".is-invalid");
        if (firstErr) {
          firstErr.focus();
          firstErr.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        if (window.fxToast) {
          window.fxToast("Please complete all required fields correctly before submitting.", "warning");
        }
      }
    });
  }
  function initDocumentUploadForm(root) {
    var form = (root && root.id === "document-upload-form")
      ? root
      : (root ? root.querySelector("#document-upload-form") : null);
    if (!form || form.dataset.docValidationInitialized === "true") return;
    form.dataset.docValidationInitialized = "true";

    var fileInput = form.querySelector("input[name='file'], input[type='file']");
    var typeSelect = form.querySelector("select[name='doc_type']");

    if (!fileInput || !typeSelect) return;

    var imageExts = ["jpg", "jpeg", "png", "webp", "gif"];

    function updateAcceptAttr() {
      var docType = typeSelect.value;
      if (docType === "PHOTO") {
        fileInput.setAttribute("accept", "image/png,image/jpeg,image/webp,image/gif,.jpg,.jpeg,.png,.webp");
      } else if (docType === "PDF") {
        fileInput.setAttribute("accept", ".pdf,application/pdf");
      } else {
        fileInput.setAttribute("accept", ".pdf,image/png,image/jpeg,image/webp,image/gif,.docx,.xlsx,.txt,.csv");
      }
    }

    updateAcceptAttr();

    function validateFile() {
      var docType = typeSelect.value;
      if (!fileInput.files || fileInput.files.length === 0) {
        setFieldError(fileInput, "Please choose a file to upload.");
        return false;
      }
      var file = fileInput.files[0];
      var name = file.name || "";
      var ext = name.indexOf(".") !== -1 ? name.split(".").pop().toLowerCase() : "";

      if (file.size === 0) {
        setFieldError(fileInput, "The uploaded file is empty.");
        return false;
      }
      if (file.size > 25 * 1024 * 1024) {
        setFieldError(fileInput, "File exceeds the 25 MB limit.");
        return false;
      }

      if (docType === "PHOTO") {
        if (imageExts.indexOf(ext) === -1) {
          setFieldError(fileInput, "Selected document type is Photograph. Please upload a valid image file (.jpg, .jpeg, .png, .webp).");
          return false;
        }
      } else if (docType === "PDF") {
        if (ext !== "pdf") {
          setFieldError(fileInput, "Selected document type is PDF. Please upload a valid PDF file (.pdf).");
          return false;
        }
      } else if (docType === "OTHER") {
        var allowedOther = ["pdf", "jpg", "jpeg", "png", "webp", "gif", "docx", "xlsx", "txt", "csv"];
        if (allowedOther.indexOf(ext) === -1) {
          setFieldError(fileInput, "File type '." + ext + "' is not supported. Allowed formats: PDF, images, Office documents, text/CSV.");
          return false;
        }
      }

      clearFieldError(fileInput);
      return true;
    }

    typeSelect.addEventListener("change", function () {
      updateAcceptAttr();
      if (fileInput.files && fileInput.files.length > 0) {
        validateFile();
      }
    });

    fileInput.addEventListener("change", function () {
      if (this.files && this.files.length > 0) {
        validateFile();
      } else {
        setFieldError(this, "Please choose a file to upload.");
      }
    });

    form.addEventListener("submit", function (e) {
      if (!validateFile()) {
        e.preventDefault();
        e.stopImmediatePropagation();
        fileInput.focus();
        if (window.fxToast) {
          window.fxToast("Please select a valid file matching the chosen document type.", "warning");
        }
        return false;
      }
    });
  }

  // Hook into lifecycle events
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initSiteForm(document);
      initAssetForm(document);
      initMemberInviteForm(document);
      initDocumentUploadForm(document);
    });
  } else {
    initSiteForm(document);
    initAssetForm(document);
    initMemberInviteForm(document);
    initDocumentUploadForm(document);
  }

  // Hook into HTMX swaps
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    if (evt.detail && evt.detail.target) {
      initSiteForm(evt.detail.target);
      initAssetForm(evt.detail.target);
      initMemberInviteForm(evt.detail.target);
      initDocumentUploadForm(evt.detail.target);
    }
  });

  // Hook into Bootstrap modal open
  document.addEventListener("shown.bs.modal", function (evt) {
    if (evt.target && (evt.target.id === "siteModal" || evt.target.querySelector("#site-modal-form"))) {
      initSiteForm(evt.target);
    }
    if (evt.target && (evt.target.id === "assetModal" || evt.target.querySelector("#asset-modal-form"))) {
      initAssetForm(evt.target);
    }
  });

  // Global Delegated Country-to-State & State-to-City Cascading & Visibility Guard
  document.addEventListener("change", function (e) {
    if (e.target && e.target.id === "id_country") {
      var form = e.target.closest("form");
      if (form) {
        var stateEl = form.querySelector("#id_state_region");
        var cityEl = form.querySelector("#id_city");
        var stateWrapper = form.querySelector("#field-wrapper-state") || (stateEl ? stateEl.closest(".col-md-6") : null);
        var cityWrapper = form.querySelector("#field-wrapper-city") || (cityEl ? cityEl.closest(".col-md-6") : null);
        var country = (e.target.value || "").trim().toUpperCase();

        if (stateEl) {
          var states = geoStates[country] || [];
          stateEl.innerHTML = "";
          var defStateOpt = document.createElement("option");
          defStateOpt.value = "";
          defStateOpt.textContent = "Select State / Region...";
          stateEl.appendChild(defStateOpt);
          states.forEach(function (s) {
            var opt = document.createElement("option");
            opt.value = s;
            opt.textContent = s;
            stateEl.appendChild(opt);
          });
          stateEl.value = "";
        }

        if (cityEl) {
          cityEl.innerHTML = '<option value="">Select City...</option>';
          cityEl.value = "";
        }

        if (stateWrapper) {
          if (country) {
            stateWrapper.classList.remove("d-none");
            stateWrapper.style.display = "";
          } else {
            stateWrapper.classList.add("d-none");
            stateWrapper.style.display = "none";
          }
        }

        if (cityWrapper) {
          cityWrapper.classList.add("d-none");
          cityWrapper.style.display = "none";
        }
      }
    } else if (e.target && e.target.id === "id_state_region") {
      var form = e.target.closest("form");
      if (form) {
        var cityEl = form.querySelector("#id_city");
        var cityWrapper = form.querySelector("#field-wrapper-city") || (cityEl ? cityEl.closest(".col-md-6") : null);
        var state = (e.target.value || "").trim();

        if (cityEl) {
          var cities = geoCities[state] || [];
          cityEl.innerHTML = "";
          var defaultOpt = document.createElement("option");
          defaultOpt.value = "";
          defaultOpt.textContent = "Select City...";
          cityEl.appendChild(defaultOpt);
          cities.forEach(function (c) {
            var opt = document.createElement("option");
            opt.value = c;
            opt.textContent = c;
            cityEl.appendChild(opt);
          });
          cityEl.value = "";
        }

        if (cityWrapper) {
          if (state) {
            cityWrapper.classList.remove("d-none");
            cityWrapper.style.display = "";
          } else {
            cityWrapper.classList.add("d-none");
            cityWrapper.style.display = "none";
          }
        }
      }
    }
  });

  document.addEventListener("mousedown", function (e) {
    if (e.target && e.target.id === "id_city") {
      var form = e.target.closest("form");
      if (form) {
        var stateEl = form.querySelector("#id_state_region");
        if (stateEl && stateEl.value) {
          var state = stateEl.value;
          var cities = geoCities[state] || [];
          if (cities.length > 0) {
            var existing = Array.from(e.target.options).map(function (o) { return o.value; });
            var isMissing = cities.some(function (c) { return existing.indexOf(c) === -1; });
            if (isMissing) {
              var cur = e.target.value;
              e.target.innerHTML = "";
              var defOpt = document.createElement("option");
              defOpt.value = "";
              defOpt.textContent = "Select City...";
              e.target.appendChild(defOpt);
              cities.forEach(function (c) {
                var opt = document.createElement("option");
                opt.value = c;
                opt.textContent = c;
                if (c === cur) opt.selected = true;
                e.target.appendChild(opt);
              });
            }
          }
        }
      }
    }
  });

  // Live validation for Workflow Action reason inputs (e.g. Start maintenance)
  document.addEventListener("input", function (e) {
    if (e.target && e.target.name === "reason" && (e.target.closest(".fx-workflow-bar") || e.target.closest("form"))) {
      var input = e.target;
      var val = input.value;
      if (/\d/.test(val)) {
        input.setCustomValidity("Reason must contain only alphabetical characters and cannot contain numbers.");
        input.classList.add("is-invalid");
      } else {
        input.setCustomValidity("");
        input.classList.remove("is-invalid");
      }
    }
  });

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form) {
      var reasonInput = form.querySelector("input[name='reason']");
      if (reasonInput) {
        var val = (reasonInput.value || "").trim();
        if (/\d/.test(val)) {
          e.preventDefault();
          e.stopImmediatePropagation();
          reasonInput.setCustomValidity("Reason must contain only alphabetical characters and cannot contain numbers.");
          reasonInput.classList.add("is-invalid");
          reasonInput.reportValidity();
          return false;
        }
      }
    }
  });

  // Enterprise Login Password Visibility Toggle
  document.addEventListener("click", function (e) {
    var toggle = e.target.closest("#fx-pw-toggle");
    if (!toggle) return;
    e.preventDefault();
    var pwInput = document.getElementById("id_password");
    var eyeIcon = document.getElementById("fx-pw-icon-eye");
    var eyeOffIcon = document.getElementById("fx-pw-icon-eye-off");
    if (pwInput) {
      var isPassword = pwInput.getAttribute("type") === "password";
      pwInput.setAttribute("type", isPassword ? "text" : "password");
      // if (eyeIcon) eyeIcon.style.display = isPassword ? "none" : "block";
      // if (eyeOffIcon) eyeOffIcon.style.display = isPassword ? "block" : "none";
      // toggle.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
    }
  });
  // Prevent decimal/exponent characters on integer/whole-number inputs with step="1"
  document.addEventListener("keydown", function (e) {
    if (e.target && e.target.matches && e.target.matches('input[type="number"][step="1"]')) {
      if (['.', 'e', 'E', '+', ','].includes(e.key)) {
        e.preventDefault();
      }
      if (e.target.min && parseFloat(e.target.min) >= 0 && e.key === '-') {
        e.preventDefault();
      }
    }
  });
})();

// Global loading bar during HTMX navigation, filtering and swaps
document.addEventListener("htmx:beforeRequest", function () {
  var l = document.getElementById("global-loading-indicator");
  if (l) l.classList.add("is-active");
});
document.addEventListener("htmx:afterRequest", function () {
  var l = document.getElementById("global-loading-indicator");
  if (l) l.classList.remove("is-active");
});
document.addEventListener("htmx:requestError", function () {
  var l = document.getElementById("global-loading-indicator");
  if (l) l.classList.remove("is-active");
});
