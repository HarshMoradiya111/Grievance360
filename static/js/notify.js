/* ===========================================================================
   Grievance360 - Live In-Window Notification Engine
   
   Features:
   1. Live polling (every 5s) without requiring full page reload.
   2. Floating in-window Toast pop-ups for live admin updates and status changes.
   3. Handles both logged-in users and guest users (tracking ticket from localStorage).
   4. Catch-up notification: If user logs in 5+ hours after admin updated status,
      the window pop-up displays with accurate relative time period (e.g. "5 hours ago").
   5. Synthesized audio chime (Web Audio API) & native Desktop Notification API.
   =========================================================================== */
(function () {
  "use strict";

  var POLL_MS = 5000;
  var body = document.body;
  var isAuthenticated = body && body.getAttribute("data-authenticated") === "1";
  var toastContainer = document.getElementById("geToastContainer");
  var countBadge = document.getElementById("notifCount");
  var list = document.getElementById("notifList");
  var markReadButton = document.getElementById("notifMarkRead");

  // Keep track of previously seen notification IDs in memory & session
  var knownIds = new Set();
  var isInitialFetch = true;

  // ---------------------------------------------------------------------------
  // Web Audio Chime Generator
  // ---------------------------------------------------------------------------
  function playNotificationChime() {
    try {
      var AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!AudioContext) return;
      var ctx = new AudioContext();
      if (ctx.state === "suspended") {
        ctx.resume();
      }
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = "sine";
      // 2-tone melodic chime: 659.25Hz (E5) -> 880Hz (A5)
      osc.frequency.setValueAtTime(659.25, ctx.currentTime);
      osc.frequency.setValueAtTime(880.00, ctx.currentTime + 0.12);
      gain.gain.setValueAtTime(0.09, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.45);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.48);
    } catch (e) {
      // Audio autoplay policy might prevent sound before user interacts
    }
  }

  // ---------------------------------------------------------------------------
  // Desktop Native Notification
  // ---------------------------------------------------------------------------
  function triggerDesktopNotification(title, message, link) {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") {
      try {
        var n = new Notification(title, {
          body: message,
          icon: "https://www.charusat.ac.in/images/logo.png"
        });
        if (link) {
          n.onclick = function () {
            window.focus();
            window.location.href = link;
          };
        }
      } catch (err) {}
    } else if (Notification.permission !== "denied") {
      try {
        Notification.requestPermission();
      } catch (err) {}
    }
  }

  // ---------------------------------------------------------------------------
  // Floating In-Window Toast Pop-up Generator
  // ---------------------------------------------------------------------------
  function showToast(options) {
    if (!toastContainer) {
      toastContainer = document.createElement("div");
      toastContainer.id = "geToastContainer";
      toastContainer.className = "toast-container position-fixed top-0 end-0 p-3";
      toastContainer.style.zIndex = "1095";
      document.body.appendChild(toastContainer);
    }

    var title = options.title || "Grievance Update";
    var message = options.message || "";
    var timeAgo = options.timeAgo || "Just now";
    var link = options.link || null;
    var notifId = options.id || null;
    var statusColor = options.statusColor || "primary";

    var toastEl = document.createElement("div");
    toastEl.className = "toast ge-toast";
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");

    var iconClass = "bi-bell-fill text-primary";
    if (statusColor === "success") iconClass = "bi-check-circle-fill text-success";
    else if (statusColor === "warning") iconClass = "bi-exclamation-triangle-fill text-warning";
    else if (statusColor === "danger") iconClass = "bi-exclamation-circle-fill text-danger";
    else if (statusColor === "info") iconClass = "bi-info-circle-fill text-info";

    var html =
      '<div class="toast-header ge-toast-header d-flex align-items-center">' +
        '<i class="bi ' + iconClass + ' me-2 fs-6"></i>' +
        '<strong class="me-auto text-truncate" style="max-width:180px;">' + escapeHtml(title) + '</strong>' +
        '<span class="ge-toast-time me-2"><i class="bi bi-clock"></i> ' + escapeHtml(timeAgo) + '</span>' +
        '<button type="button" class="btn-close btn-close-sm" data-bs-dismiss="toast" aria-label="Close"></button>' +
      '</div>' +
      '<div class="toast-body ge-toast-body">' +
        '<div class="ge-wrap">' + escapeHtml(message) + '</div>';

    if (link) {
      html +=
        '<div class="mt-2 text-end">' +
          '<a href="' + encodeURI(link) + '" class="ge-toast-action">' +
            'View Ticket <i class="bi bi-arrow-right"></i>' +
          '</a>' +
        '</div>';
    }

    html += '</div>';
    toastEl.innerHTML = html;
    toastContainer.appendChild(toastEl);

    // Bootstrap Toast Initialization
    var bsToast = null;
    if (window.bootstrap && window.bootstrap.Toast) {
      bsToast = new window.bootstrap.Toast(toastEl, {
        autohide: true,
        delay: 9000
      });
      bsToast.show();
    } else {
      toastEl.classList.add("show");
    }

    // Play Melodic Chime & Native OS notification
    playNotificationChime();
    if (document.hidden) {
      triggerDesktopNotification(title, message, link);
    }

    // Mark as read in server if clicked or dismissed
    if (notifId && isAuthenticated) {
      toastEl.addEventListener("click", function (e) {
        if (!e.target.classList.contains("btn-close")) {
          fetch("/api/notifications/" + notifId + "/read", { method: "POST" }).catch(function () {});
        }
      });
    }

    // Remove element on hide
    toastEl.addEventListener("hidden.bs.toast", function () {
      if (toastEl.parentNode) {
        toastEl.parentNode.removeChild(toastEl);
      }
    });

    return toastEl;
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  // ---------------------------------------------------------------------------
  // Logged-in User Notification Engine
  // ---------------------------------------------------------------------------
  function renderBell(data) {
    if (!countBadge || !list) return;

    if (data.unread > 0) {
      countBadge.textContent = data.unread > 99 ? "99+" : data.unread;
      countBadge.classList.remove("d-none");
    } else {
      countBadge.classList.add("d-none");
    }

    if (!data.items || data.items.length === 0) {
      list.innerHTML =
        '<div class="dropdown-item-text text-muted small">No notifications yet.</div>';
      return;
    }

    var html = "";
    data.items.forEach(function (item) {
      var classes = "ge-notif-item" + (item.is_read ? "" : " unread");
      var timeDisplay = item.time_ago || item.at || "";
      var body =
        '<div class="small fw-medium">' + escapeHtml(item.message) + '</div>' +
        '<div class="text-muted d-flex align-items-center gap-1" style="font-size:.7rem">' +
          '<i class="bi bi-clock"></i> ' + escapeHtml(timeDisplay) +
        '</div>';

      html += item.link
        ? '<a class="' + classes + ' d-block text-decoration-none text-body" href="' +
            encodeURI(item.link) + '">' + body + '</a>'
        : '<div class="' + classes + '">' + body + '</div>';
    });
    list.innerHTML = html;
  }

  function handleNotifications(data) {
    renderBell(data);

    if (!data.items || data.items.length === 0) {
      isInitialFetch = false;
      return;
    }

    // Determine which notifications need to pop up
    data.items.forEach(function (item, index) {
      var id = item.id;
      var sessionKey = "g360_seen_notif_" + id;
      var hasBeenSeenThisSession = sessionStorage.getItem(sessionKey);

      // On Initial page load (e.g. user logs in 5 hours later):
      // Pop up any unread notification that hasn't been toasted in this browser session.
      // On Subsequent live polls:
      // Pop up any brand new notification that just arrived.
      var shouldPop = false;

      if (isInitialFetch) {
        if (!item.is_read && !hasBeenSeenThisSession) {
          shouldPop = true;
        }
      } else {
        if (!knownIds.has(id) && !hasBeenSeenThisSession) {
          shouldPop = true;
        }
      }

      if (shouldPop) {
        sessionStorage.setItem(sessionKey, "1");
        // Stagger popups by 350ms so multiple updates don't overlap awkwardly
        setTimeout(function () {
          showToast({
            id: item.id,
            title: item.ticket_code ? "Ticket " + item.ticket_code : "Complaint Update",
            message: item.message,
            timeAgo: item.time_ago || "Just now",
            link: item.link,
            statusColor: item.status_color || "primary"
          });
        }, index * 350);
      }

      knownIds.add(id);
    });

    isInitialFetch = false;
  }

  function pollAuth() {
    fetch("/api/notifications", { headers: { "Accept": "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(handleNotifications)
      .catch(function () {});
  }

  // ---------------------------------------------------------------------------
  // Unauthenticated / Guest User Notification Engine
  // ---------------------------------------------------------------------------
  function pollGuest() {
    // Check if guest user has a tracked ticket saved in localStorage
    var trackedTicket = localStorage.getItem("g360_tracked_ticket") || "";
    var query = trackedTicket ? "?ticket_code=" + encodeURIComponent(trackedTicket) : "";

    fetch("/api/public/notifications" + query, { headers: { "Accept": "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        // Handle tracked complaint updates for guests
        if (data.updates && data.updates.length > 0) {
          data.updates.forEach(function (up) {
            var cacheKey = "g360_guest_status_" + up.ticket_code;
            var prevStatus = localStorage.getItem(cacheKey);

            if (prevStatus && prevStatus !== up.status) {
              // Status was changed by admin live!
              localStorage.setItem(cacheKey, up.status);
              showToast({
                title: "Ticket " + up.ticket_code + " Updated",
                message: "Status changed to " + up.status + (up.remark ? " — " + up.remark : ""),
                timeAgo: up.time_ago || "Just now",
                link: up.link || "/track/" + up.ticket_code,
                statusColor: up.status_color || "info"
              });
            } else if (!prevStatus) {
              localStorage.setItem(cacheKey, up.status);
              // On first check, if updated recently, toast
              var sessionKey = "g360_seen_guest_" + up.ticket_code;
              if (!sessionStorage.getItem(sessionKey)) {
                sessionStorage.setItem(sessionKey, "1");
                showToast({
                  title: "Ticket " + up.ticket_code,
                  message: "Current status: " + up.status + (up.remark ? " — " + up.remark : ""),
                  timeAgo: up.time_ago || "Just now",
                  link: up.link || "/track/" + up.ticket_code,
                  statusColor: up.status_color || "info"
                });
              }
            }
          });
        }

        // Handle Campus Announcements for guests
        if (data.announcements && data.announcements.length > 0) {
          data.announcements.forEach(function (ann, i) {
            var sessionKey = "g360_seen_ann_" + ann.id;
            if (!sessionStorage.getItem(sessionKey)) {
              sessionStorage.setItem(sessionKey, "1");
              setTimeout(function () {
                showToast({
                  id: ann.id,
                  title: "Campus Notice",
                  message: ann.title + (ann.message ? ": " + ann.message : ""),
                  timeAgo: ann.time_ago || "Just now",
                  link: ann.link || "/announcements",
                  statusColor: "warning"
                });
              }, i * 400);
            }
          });
        }
      })
      .catch(function () {});
  }

  // ---------------------------------------------------------------------------
  // Bell 'Mark All Read' Handler
  // ---------------------------------------------------------------------------
  if (markReadButton) {
    markReadButton.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      fetch("/api/notifications/read", { method: "POST" })
        .then(function () {
          if (countBadge) countBadge.classList.add("d-none");
          document.querySelectorAll(".ge-notif-item.unread").forEach(function (el) {
            el.classList.remove("unread");
          });
        })
        .catch(function () {});
    });
  }

  // ---------------------------------------------------------------------------
  // Global Export for other scripts (track.js, live.js)
  // ---------------------------------------------------------------------------
  window.Grievance360Notify = {
    showToast: showToast,
    playChime: playNotificationChime,
    triggerDesktop: triggerDesktopNotification
  };

  // ---------------------------------------------------------------------------
  // Start Polling Engine
  // ---------------------------------------------------------------------------
  if (isAuthenticated) {
    pollAuth();
    setInterval(pollAuth, POLL_MS);
  } else {
    pollGuest();
    setInterval(pollGuest, POLL_MS + 2000);
  }
})();
