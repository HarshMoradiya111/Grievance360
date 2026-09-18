/* ===========================================================================
   Grievance360 - notification bell.

   Polls /api/notifications and keeps the unread count + dropdown list fresh
   without ever reloading the page. Loaded from base.html for every logged-in
   user, so the bell works on every screen.
   =========================================================================== */
(function () {
  "use strict";

  var POLL_MS = 15000;          // 15s: often enough to feel live, light on the DB
  var countBadge = document.getElementById("notifCount");
  var list = document.getElementById("notifList");
  var markReadButton = document.getElementById("notifMarkRead");

  // The bell only exists for logged-in users, so bail out quietly otherwise.
  if (!countBadge || !list) { return; }

  function escapeHtml(text) {
    // Notification text comes from complaint subjects, i.e. user input.
    // Escaping here means a subject containing HTML can never run as markup.
    var div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  }

  function render(data) {
    // -- unread badge ------------------------------------------------------
    if (data.unread > 0) {
      countBadge.textContent = data.unread > 99 ? "99+" : data.unread;
      countBadge.classList.remove("d-none");
    } else {
      countBadge.classList.add("d-none");
    }

    // -- dropdown list -----------------------------------------------------
    if (!data.items || data.items.length === 0) {
      list.innerHTML =
        '<div class="dropdown-item-text text-muted small">No notifications yet.</div>';
      return;
    }

    var html = "";
    data.items.forEach(function (item) {
      var classes = "ge-notif-item" + (item.is_read ? "" : " unread");
      var body =
        '<div class="small">' + escapeHtml(item.message) + "</div>" +
        '<div class="text-muted" style="font-size:.7rem">' +
        escapeHtml(item.at) + "</div>";

      html += item.link
        ? '<a class="' + classes + ' d-block text-decoration-none text-body" href="' +
          encodeURI(item.link) + '">' + body + "</a>"
        : '<div class="' + classes + '">' + body + "</div>";
    });
    list.innerHTML = html;
  }

  function poll() {
    fetch("/api/notifications", { headers: { "Accept": "application/json" } })
      .then(function (response) {
        if (!response.ok) { throw new Error("HTTP " + response.status); }
        return response.json();
      })
      .then(render)
      .catch(function () {
        // A failed poll is not worth shouting about -- the next one may work.
        // We deliberately leave the last known state on screen.
      });
  }

  if (markReadButton) {
    markReadButton.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();          // keep the dropdown open
      fetch("/api/notifications/read", { method: "POST" })
        .then(function () { poll(); })
        .catch(function () {});
    });
  }

  poll();                                // once immediately
  setInterval(poll, POLL_MS);            // then on a timer
})();
