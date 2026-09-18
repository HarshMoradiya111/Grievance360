/* ===========================================================================
   Grievance360 - live status polling on the track page.

   Every 5 seconds this asks the JSON API for the complaint's current status
   and updates the badge in place. If the number of history entries grows --
   meaning staff added a new step -- the page reloads once so the timeline is
   rebuilt by the server rather than duplicated here in JavaScript.

   Config arrives through data-* attributes on the <script> tag, so no server
   values are ever inlined into executable JS.
   =========================================================================== */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) { return; }

  var statusUrl = script.getAttribute("data-status-url");
  var knownHistoryCount = parseInt(script.getAttribute("data-history-count"), 10) || 0;
  var POLL_MS = 5000;

  var badge = document.getElementById("statusBadge");
  var liveDot = document.getElementById("liveDot");
  var deadlineText = document.getElementById("deadlineText");
  var slaLine = document.getElementById("slaLine");

  if (!statusUrl || !badge) { return; }

  function setLive(isLive) {
    if (!liveDot) { return; }
    liveDot.className = isLive ? "small text-muted ms-auto"
                               : "small text-danger ms-auto";
    liveDot.innerHTML = isLive
      ? '<i class="bi bi-broadcast"></i> live'
      : '<i class="bi bi-wifi-off"></i> offline';
  }

  function applyStatus(data) {
    setLive(true);

    // Swap the badge text and its Bootstrap colour class.
    if (badge.textContent.trim() !== data.status) {
      badge.textContent = data.status;
      badge.className = "badge bg-" + data.status_color;
      // A short pulse so the change is noticed without being obnoxious.
      badge.style.transition = "transform .2s ease";
      badge.style.transform = "scale(1.15)";
      setTimeout(function () { badge.style.transform = "scale(1)"; }, 220);
    }

    if (deadlineText) { deadlineText.textContent = data.deadline; }

    if (slaLine) {
      if (data.breached) {
        slaLine.innerHTML =
          '<span class="text-danger small fw-semibold">' +
          '<i class="bi bi-exclamation-octagon"></i> SLA breached ' +
          Math.abs(data.days_left) + " day(s) ago</span>";
      } else {
        slaLine.innerHTML =
          '<span class="text-muted small"><i class="bi bi-clock"></i> ' +
          data.days_left + " day(s) left &middot; due " + data.deadline + "</span>";
      }
    }

    // New history rows exist -> let the server re-render the timeline.
    if (data.history_count > knownHistoryCount) {
      knownHistoryCount = data.history_count;
      window.location.reload();
    }
  }

  function poll() {
    fetch(statusUrl, { headers: { "Accept": "application/json" } })
      .then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status); }
        return response.json();
      })
      .then(applyStatus)
      .catch(function () { setLive(false); });
  }

  poll();
  setInterval(poll, POLL_MS);
})();
