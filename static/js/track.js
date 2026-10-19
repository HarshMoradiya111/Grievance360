/* ===========================================================================
   Grievance360 - Live Complaint Tracker (In-Place DOM Update)
   
   Polls status endpoint every 5 seconds.
   Dynamically updates status badge, SLA countdown, and timeline in place
   WITHOUT reloading the page! Triggers window toast pop-ups on live updates.
   =========================================================================== */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) return;

  var isPublicMode = script.getAttribute("data-public-mode") === "1";
  var ticketCode = script.getAttribute("data-ticket-code") || "";
  var statusUrl = script.getAttribute("data-status-url");
  var knownHistoryCount = parseInt(script.getAttribute("data-history-count"), 10) || 0;
  var prevStatus = null;
  var POLL_MS = 5000;

  if (isPublicMode && ticketCode && !statusUrl) {
    statusUrl = "/api/public/complaint/" + encodeURIComponent(ticketCode) + "/status";
  }

  var badge = document.getElementById("statusBadge");
  var liveDot = document.getElementById("liveDot");
  var deadlineText = document.getElementById("deadlineText");
  var slaLine = document.getElementById("slaLine");
  var timelineEl = document.getElementById("timeline");

  var resSubject = document.getElementById("resSubject");
  var resCategory = document.getElementById("resCategory");
  var resUpdated = document.getElementById("resUpdated");
  var resTicketCode = document.getElementById("resTicketCode");
  var trackResult = document.getElementById("trackResult");

  if (!statusUrl) return;

  function setLive(isLive) {
    if (!liveDot) return;
    liveDot.className = isLive ? "small text-muted ms-auto" : "small text-danger ms-auto";
    liveDot.innerHTML = isLive
      ? '<i class="bi bi-broadcast text-success"></i> live'
      : '<i class="bi bi-wifi-off text-danger"></i> reconnecting...';
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function renderTimeline(history) {
    if (!timelineEl || !history || history.length === 0) return;
    var html = "";
    history.forEach(function (entry, idx) {
      var isLast = idx === history.length - 1;
      var color = entry.status_color || "secondary";
      var timeStr = entry.time_ago || entry.created_at || "";

      html +=
        '<li class="ge-timeline-item ' + (isLast ? "is-current" : "") + '">' +
          '<div class="d-flex flex-wrap align-items-center gap-2">' +
            '<span class="badge bg-' + color + '">' + escapeHtml(entry.new_status) + '</span>';
      if (entry.old_status) {
        html += '<span class="text-muted" style="font-size:.72rem">from ' + escapeHtml(entry.old_status) + '</span>';
      }
      html += '</div>';

      if (entry.remark) {
        html += '<div class="small ge-wrap mt-1">' + escapeHtml(entry.remark) + '</div>';
      }

      html +=
        '<div class="text-muted mt-1" style="font-size:.72rem">' +
          escapeHtml(entry.changed_by_name || "System") + ' &middot; ' +
          '<span class="fw-medium"><i class="bi bi-clock"></i> ' + escapeHtml(timeStr) + '</span>' +
        '</div>' +
      '</li>';
    });
    timelineEl.innerHTML = html;
  }

  function applyStatus(data) {
    setLive(true);
    if (!data || !data.status) return;

    // Cache ticket in localStorage for guest/background push notifications
    if (data.ticket_code) {
      localStorage.setItem("g360_tracked_ticket", data.ticket_code);
    }

    // Public mode field updates
    if (isPublicMode) {
      if (trackResult) trackResult.classList.remove("d-none");
      if (resTicketCode) resTicketCode.textContent = data.ticket_code;
      if (resSubject && data.subject) resSubject.textContent = data.subject;
      if (resCategory && data.category_name) resCategory.textContent = data.category_name;
      if (resUpdated) resUpdated.textContent = (data.updated_time_ago ? data.updated_time_ago + " (" + data.updated_at + ")" : data.updated_at);
    }

    var isInitial = (prevStatus === null);
    var statusChanged = (prevStatus !== null && prevStatus !== data.status);
    var historyAdded = (data.history_count > knownHistoryCount);

    // Update Badge in place with animation
    if (badge && (badge.textContent.trim() !== data.status || statusChanged)) {
      badge.textContent = data.status;
      badge.className = "badge bg-" + (data.status_color || "primary") + " ge-pulse-badge";
    }

    // Update Deadline
    if (deadlineText && data.deadline) {
      deadlineText.textContent = data.deadline;
    }

    // Update SLA line
    if (slaLine) {
      if (data.breached) {
        slaLine.innerHTML =
          '<span class="text-danger small fw-semibold">' +
          '<i class="bi bi-exclamation-octagon"></i> SLA breached ' +
          Math.abs(data.days_left) + ' day(s) ago</span>';
      } else {
        slaLine.innerHTML =
          '<span class="text-muted small"><i class="bi bi-clock"></i> ' +
          data.days_left + ' day(s) left &middot; due ' + data.deadline + '</span>';
      }
    }

    // Dynamically update the timeline in DOM WITHOUT reload!
    if (data.history && (historyAdded || isInitial)) {
      renderTimeline(data.history);
      knownHistoryCount = data.history_count;
    }

    // If status changed live while viewing: Show in-window notification popup!
    if (statusChanged && !isInitial) {
      var lastRemark = data.last_update && data.last_update.remark ? " — " + data.last_update.remark : "";
      var timeAgo = data.updated_time_ago || "Just now";

      if (window.Grievance360Notify && window.Grievance360Notify.showToast) {
        window.Grievance360Notify.showToast({
          title: "Status Updated: " + data.status,
          message: data.ticket_code + " status changed from " + prevStatus + " to " + data.status + lastRemark,
          timeAgo: timeAgo,
          statusColor: data.status_color || "primary"
        });
      }
    }

    prevStatus = data.status;
  }

  function poll() {
    fetch(statusUrl, { headers: { "Accept": "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(applyStatus)
      .catch(function () {
        setLive(false);
      });
  }

  poll();
  setInterval(poll, POLL_MS);
})();
