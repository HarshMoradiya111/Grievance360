/* ===========================================================================
   Grievance360 - live dashboard stats.

   Detects the current page type from a [data-live-page] attribute on the
   stat-tile row, hits the matching JSON endpoint every 20 s, and updates
   the number in each tile without touching the rest of the page.

   Also refreshes the complaint-card section when the server reports a
   different complaint count (new submission or status change by staff).
   =========================================================================== */
(function () {
  "use strict";

  var POLL_MS   = 6000;    // 6 s between ticks for responsive live stats
  var FAST_MS   = 3000;    // 3 s right after a detected change
  var timer     = null;
  var liveBar   = document.getElementById("liveBar");

  // Locate the stat row and decide which endpoint to hit.
  var row = document.querySelector("[data-live-page]");
  if (!row) { return; }

  var page = row.getAttribute("data-live-page");
  var endpoints = {
    student : "/api/live/dashboard",
    admin   : "/api/live/admin_stats",
    staff   : "/api/live/staff_stats"
  };
  var endpoint = endpoints[page];
  if (!endpoint) { return; }

  // Cache the previous total so we know when something changed.
  var prevTotal = null;

  // ---- dot indicator -------------------------------------------------------
  function setDot(ok) {
    if (!liveBar) { return; }
    if (ok) {
      liveBar.innerHTML =
        '<i class="bi bi-broadcast text-success"></i>' +
        '<span class="text-muted ms-1" style="font-size:.72rem">live</span>';
    } else {
      liveBar.innerHTML =
        '<i class="bi bi-wifi-off text-danger"></i>' +
        '<span class="text-muted ms-1" style="font-size:.72rem">offline</span>';
    }
  }

  // ---- apply a single JSON response to the DOM ----------------------------
  function apply(data) {
    setDot(true);

    // Update every stat tile that has a matching data-live-key.
    document.querySelectorAll("[data-live-key]").forEach(function (el) {
      var key = el.getAttribute("data-live-key");
      if (data[key] !== undefined) {
        var next = String(data[key]);
        if (el.textContent.trim() !== next) {
          el.textContent = next;
          // brief pop animation so the change is noticeable
          el.style.transition = "transform .2s ease";
          el.style.transform  = "scale(1.18)";
          setTimeout(function () { el.style.transform = "scale(1)"; }, 220);
        }
      }
    });

    // If the complaint count changed, notify user without disrupting their screen
    var total = data["total"] !== undefined ? data["total"] : null;
    if (prevTotal !== null && total !== null && total !== prevTotal) {
      if (window.Grievance360Notify && window.Grievance360Notify.showToast) {
        window.Grievance360Notify.showToast({
          title: "Dashboard Synced",
          message: "Live grievance metrics updated without reloading.",
          timeAgo: "Just now",
          statusColor: "info"
        });
      }
    }
    prevTotal = total;

    // Re-arm at normal interval.
    schedule(POLL_MS);
  }

  // ---- schedule next tick --------------------------------------------------
  function schedule(ms) {
    clearTimeout(timer);
    timer = setTimeout(poll, ms);
  }

  // ---- fetch ---------------------------------------------------------------
  function poll() {
    fetch(endpoint, { headers: { "Accept": "application/json" } })
      .then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.json();
      })
      .then(apply)
      .catch(function () {
        setDot(false);
        schedule(POLL_MS);   // retry at normal interval even after error
      });
  }

  poll();   // fire immediately on page load
})();
