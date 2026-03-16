// SmartApprove — main.js  (v3.1 — real-time notifications)

// ══════════════════════════════════════════════════
//  TOAST SYSTEM
// ══════════════════════════════════════════════════

function showToast(title, body, type, requestId, notifId) {
  body      = body      || "";
  type      = type      || "info";
  requestId = requestId || null;
  notifId   = notifId   || null;

  const container = document.getElementById("toast-container");
  if (!container) return;

  const icons = { success:"✅", error:"❌", info:"ℹ️", warning:"⚠️", approval:"📋" };

  const toast = document.createElement("div");
  toast.className = "toast toast-" + type;
  toast.style.cssText = "cursor:pointer;";

  toast.innerHTML =
    '<div style="display:flex;gap:10px;align-items:flex-start;width:100%;">' +
      '<span style="font-size:18px;flex-shrink:0;">' + (icons[type]||"ℹ️") + '</span>' +
      '<div style="flex:1;min-width:0;">' +
        '<div style="font-weight:700;font-size:13.5px;margin-bottom:2px;">' + title + '</div>' +
        (body ? '<div style="font-size:12px;opacity:0.8;line-height:1.4;">' + body + '</div>' : '') +
        (requestId ? '<div style="font-size:11px;margin-top:5px;color:#DB0011;font-weight:600;">Click to view →</div>' : '') +
      '</div>' +
      '<span class="toast-close" style="font-size:16px;opacity:0.6;flex-shrink:0;padding:0 2px;">✕</span>' +
    '</div>';

  if (requestId) {
    toast.addEventListener("click", function(e) {
      if (!e.target.classList.contains("toast-close")) {
        window.location.href = "/requests/" + requestId;
      }
    });
  }

  var closeBtn = toast.querySelector(".toast-close");
  if (closeBtn) {
    closeBtn.addEventListener("click", function(e) {
      e.stopPropagation();
      dismissToast(toast);
    });
  }

  container.appendChild(toast);

  if (notifId) {
    fetch("/api/notifications/" + notifId + "/read", { method: "POST" });
  }

  var timer = setTimeout(function() { dismissToast(toast); }, 6000);
  toast._timer = timer;
}

function dismissToast(toast) {
  clearTimeout(toast._timer);
  toast.style.opacity = "0";
  toast.style.transform = "translateX(40px)";
  toast.style.transition = "all 0.3s ease";
  setTimeout(function() { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 320);
}


// ══════════════════════════════════════════════════
//  REAL-TIME NOTIFICATION POLLING
// ══════════════════════════════════════════════════

(function() {
  if (!document.getElementById("toast-container")) return;

  var lastSeen = new Date().toISOString();
  var totalNew = 0;

  function poll() {
    fetch("/api/notifications/poll?since=" + encodeURIComponent(lastSeen))
      .then(function(res) { return res.ok ? res.json() : null; })
      .then(function(data) {
        if (!data || !data.items || data.items.length === 0) return;

        lastSeen = data.items[0].created_at;

        data.items.forEach(function(n, i) {
          setTimeout(function() {
            var type = "info";
            var t = (n.title || "").toLowerCase();
            if (t.indexOf("approved") !== -1) type = "success";
            else if (t.indexOf("rejected") !== -1) type = "error";
            else if (t.indexOf("required") !== -1 || t.indexOf("action") !== -1) type = "approval";
            showToast(n.title, n.body, type, n.request_id, n.id);
          }, i * 400);
        });

        totalNew += data.count;
        updateBell(totalNew);
      })
      .catch(function() {});
  }

  function updateBell(count) {
    var bell = document.querySelector(".notif-btn");
    if (!bell) return;
    var dot = bell.querySelector(".notif-dot");
    if (count > 0) {
      if (!dot) {
        dot = document.createElement("span");
        dot.className = "notif-dot";
        bell.appendChild(dot);
      }
      dot.textContent = count > 9 ? "9+" : String(count);
      // Shake animation
      bell.style.transform = "rotate(-15deg)";
      setTimeout(function() { bell.style.transform = "rotate(15deg)"; }, 100);
      setTimeout(function() { bell.style.transform = "rotate(0deg)";  }, 200);
      bell.style.transition = "transform 0.1s ease";
    }
  }

  // First poll after 3s, then every 15s
  setTimeout(poll, 3000);
  setInterval(poll, 15000);

  if (window.location.pathname === "/notifications") {
    totalNew = 0;
  }
})();


// ══════════════════════════════════════════════════
//  DRAG-AND-DROP FILE ZONE
// ══════════════════════════════════════════════════

document.querySelectorAll(".dropzone").forEach(function(zone) {
  zone.addEventListener("dragover",  function(e) { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", function()  { zone.classList.remove("drag-over"); });
  zone.addEventListener("drop",      function(e) {
    e.preventDefault(); zone.classList.remove("drag-over");
    var input = zone.querySelector("input[type='file']");
    if (input && e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      updateDropLabel(zone, e.dataTransfer.files);
    }
  });
  var fi = zone.querySelector("input[type='file']");
  if (fi) fi.addEventListener("change", function() { updateDropLabel(zone, fi.files); });
});

function updateDropLabel(zone, files) {
  var lbl = zone.querySelector(".dz-label");
  if (lbl && files.length) {
    var names = Array.prototype.map.call(files, function(f) { return f.name; }).join(", ");
    lbl.textContent = files.length + " file(s): " + names;
    zone.style.borderColor = "var(--red)";
    zone.style.color = "var(--red)";
  }
}


// ══════════════════════════════════════════════════
//  LIVE TABLE SEARCH
// ══════════════════════════════════════════════════

var searchInput = document.getElementById("table-search");
if (searchInput) {
  searchInput.addEventListener("input", function() {
    var term = searchInput.value.toLowerCase();
    document.querySelectorAll("tbody tr").forEach(function(row) {
      row.style.display = row.textContent.toLowerCase().indexOf(term) !== -1 ? "" : "none";
    });
  });
}


// ══════════════════════════════════════════════════
//  CONFIRM DIALOGS
// ══════════════════════════════════════════════════

document.querySelectorAll("[data-confirm]").forEach(function(el) {
  el.addEventListener("click", function(e) {
    if (!confirm(el.getAttribute("data-confirm"))) e.preventDefault();
  });
});
