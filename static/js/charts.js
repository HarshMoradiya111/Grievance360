/* ===========================================================================
   Grievance360 - analytics charts (Chart.js 4).

   Data is read from an inert <script type="application/json"> block rendered
   by admin/analytics.html, so nothing from the database is ever executed.

   Mobile-First Design Contract rule 8:
     responsive: true + maintainAspectRatio: false, with each canvas inside a
     .ge-chart-box that has a real height. Without that height the canvas
     collapses to zero pixels and the chart silently disappears.
   =========================================================================== */
(function () {
  "use strict";

  var holder = document.getElementById("analyticsData");
  if (!holder || typeof Chart === "undefined") { return; }

  var data;
  try {
    data = JSON.parse(holder.textContent);
  } catch (error) {
    return;
  }

  // Status colours deliberately mirror the Bootstrap badge colours used across
  // the app, so a slice on the pie reads as the same thing as a badge.
  var STATUS_COLORS = {
    "Pending":     "#6c757d",
    "Assigned":    "#0dcaf0",
    "In Progress": "#0d6efd",
    "Resolved":    "#198754",
    "Closed":      "#212529",
    "Reopened":    "#ffc107",
    "Rejected":    "#dc3545"
  };

  var PALETTE = ["#1e3a5f", "#2c5282", "#3182ce", "#4299e1", "#63b3ed",
                 "#f6ad55", "#ed8936", "#dd6b20", "#38a169", "#e53e3e"];

  function labelsOf(rows) { return rows.map(function (r) { return r.label; }); }
  function totalsOf(rows) { return rows.map(function (r) { return r.total; }); }

  function paletteFor(count) {
    var colors = [];
    for (var i = 0; i < count; i++) { colors.push(PALETTE[i % PALETTE.length]); }
    return colors;
  }

  var BASE_OPTIONS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { boxWidth: 12, font: { size: 11 } } }
    }
  };

  function makeChart(canvasId, config) {
    var canvas = document.getElementById(canvasId);
    if (canvas) { new Chart(canvas, config); }
  }

  // ---------------------------------------------------------------- status --
  makeChart("statusChart", {
    type: "doughnut",
    data: {
      labels: labelsOf(data.byStatus),
      datasets: [{
        data: totalsOf(data.byStatus),
        backgroundColor: data.byStatus.map(function (row) {
          return STATUS_COLORS[row.label] || "#adb5bd";
        }),
        borderWidth: 2,
        borderColor: "#fff"
      }]
    },
    options: Object.assign({}, BASE_OPTIONS, {
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } }
      }
    })
  });

  // -------------------------------------------------------------- category --
  makeChart("categoryChart", {
    type: "bar",
    data: {
      labels: labelsOf(data.byCategory),
      datasets: [{
        label: "Complaints",
        data: totalsOf(data.byCategory),
        backgroundColor: paletteFor(data.byCategory.length),
        borderRadius: 5
      }]
    },
    options: Object.assign({}, BASE_OPTIONS, {
      // Horizontal bars: category names are long, and on a 360px screen a
      // vertical bar chart turns every label into unreadable diagonal text.
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, ticks: { precision: 0 } } }
    })
  });

  // ------------------------------------------------------------ department --
  makeChart("departmentChart", {
    type: "bar",
    data: {
      labels: labelsOf(data.byDepartment),
      datasets: [{
        label: "Complaints",
        data: totalsOf(data.byDepartment),
        backgroundColor: "#2c5282",
        borderRadius: 5
      }]
    },
    options: Object.assign({}, BASE_OPTIONS, {
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
    })
  });

  // ----------------------------------------------------------------- trend --
  makeChart("trendChart", {
    type: "line",
    data: {
      labels: labelsOf(data.monthly),
      datasets: [{
        label: "Complaints raised",
        data: totalsOf(data.monthly),
        borderColor: "#1e3a5f",
        backgroundColor: "rgba(30,58,95,.12)",
        fill: true,
        tension: .3,
        pointRadius: 4
      }]
    },
    options: Object.assign({}, BASE_OPTIONS, {
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
    })
  });
})();
