/*
 * Grievance360 - module description, Word format.
 *
 * A standalone document covering the seven functional modules only.
 * Same plain academic formatting as the full report: Times New Roman,
 * 1.5 line spacing, justified body text, ruled tables, no graphics.
 *
 * Run:
 *     NODE_PATH=/c/Users/harsh/node_modules node docs/build_modules_docx.js
 */

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, WidthType, BorderStyle, ShadingType,
  PageNumber, Footer, LevelFormat, VerticalAlign,
} = require("docx");

// --------------------------------------------------------------- layout ----
const FONT = "Times New Roman";
const MONO = "Courier New";
const BODY_PT = 12;
const TABLE_PT = 10.5;

const MARGIN = { top: 1440, bottom: 1440, left: 1800, right: 1440 };
const CONTENT_W = 11906 - MARGIN.left - MARGIN.right;   // A4 text width

const half = (pt) => pt * 2;
const LINE_15 = { line: 360, lineRule: "auto" };

let listInstance = 0;
let tableNo = 0;

// ---------------------------------------------------------------- blocks ----
function para(text, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: Object.assign({ after: 160 }, LINE_15),
    children: [new TextRun({
      text, font: FONT, size: half(opts.size || BODY_PT),
      bold: !!opts.bold, italics: !!opts.italics,
    })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 200, line: 300, lineRule: "auto" },
    keepNext: true,
    children: [new TextRun({ text, font: FONT, size: half(14), bold: true,
                             color: "000000" })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120, line: 300, lineRule: "auto" },
    keepNext: true,
    children: [new TextRun({ text, font: FONT, size: half(12), bold: true,
                             italics: true, color: "000000" })],
  });
}

function bullets(items) {
  listInstance += 1;
  const instance = listInstance;
  return items.map((t) => new Paragraph({
    numbering: { reference: "bullet-list", level: 0, instance },
    alignment: AlignmentType.JUSTIFIED,
    spacing: Object.assign({ after: 100 }, LINE_15),
    children: [new TextRun({ text: t, font: FONT, size: half(BODY_PT) })],
  }));
}

function numbers(items) {
  listInstance += 1;
  const instance = listInstance;
  return items.map((t) => new Paragraph({
    numbering: { reference: "number-list", level: 0, instance },
    alignment: AlignmentType.JUSTIFIED,
    spacing: Object.assign({ after: 100 }, LINE_15),
    children: [new TextRun({ text: t, font: FONT, size: half(BODY_PT) })],
  }));
}

function mono(lines) {
  return lines.map((l, i) => new Paragraph({
    alignment: AlignmentType.LEFT,
    indent: { left: 480 },
    spacing: { after: i === lines.length - 1 ? 200 : 0, line: 260,
               lineRule: "auto" },
    keepNext: i < lines.length - 1,
    keepLines: true,
    children: [new TextRun({ text: l || " ", font: MONO, size: half(10) })],
  }));
}

const THIN = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const CELL_BORDERS = { top: THIN, bottom: THIN, left: THIN, right: THIN };

function cell(text, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders: CELL_BORDERS,
    verticalAlign: VerticalAlign.TOP,
    shading: opts.head
      ? { type: ShadingType.CLEAR, fill: "E8E8E8", color: "auto" }
      : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      spacing: { after: 0, line: 240, lineRule: "auto" },
      children: [new TextRun({
        text: String(text), font: FONT, size: half(TABLE_PT),
        bold: !!opts.head,
      })],
    })],
  });
}

/* Numbered caption above a ruled table, as in a printed report. */
function table(title, headers, rows, fractions, aligns) {
  tableNo += 1;
  const total = fractions.reduce((a, b) => a + b, 0);
  const widths = fractions.map((f) => Math.round((f / total) * CONTENT_W));
  widths[widths.length - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);

  const alignOf = (i) =>
    aligns && aligns[i] === "C" ? AlignmentType.CENTER : AlignmentType.LEFT;

  const caption = new Paragraph({
    spacing: { before: 160, after: 100 },
    keepNext: true,
    children: [new TextRun({
      text: "Table " + tableNo + "  " + title,
      font: FONT, size: half(11), bold: true,
    })],
  });

  const head = new TableRow({
    tableHeader: true,
    children: headers.map((t, i) =>
      cell(t, widths[i], { head: true, align: alignOf(i) })),
  });

  const body = rows.map((r) => new TableRow({
    children: r.map((t, i) => cell(t, widths[i], { align: alignOf(i) })),
  }));

  return [
    caption,
    new Table({
      columnWidths: widths,
      width: { size: CONTENT_W, type: WidthType.DXA },
      rows: [head].concat(body),
    }),
    new Paragraph({ spacing: { after: 200 }, children: [] }),
  ];
}

// ----------------------------------------------------------- title page ----
function titleLine(text, size, bold, spaceAfter) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: spaceAfter === undefined ? 200 : spaceAfter,
               line: 300, lineRule: "auto" },
    children: [new TextRun({
      text, font: FONT, size: half(size), bold: !!bold,
    })],
  });
}

function titlePage() {
  return [
    titleLine("GRIEVANCE360", 24, true, 160),
    titleLine("A Smart Grievance Redressal and Analytics Portal", 13, false, 40),
    titleLine("for Educational Institutions", 13, false, 800),

    titleLine("MODULE DESCRIPTION", 16, true, 800),

    titleLine("Submitted by", 12, false, 260),
    titleLine("25MSIT077", 13, true, 80),
    titleLine("25MSIT166", 13, true, 80),
    titleLine("25MSIT134", 13, true, 900),

    titleLine("MASTER OF SCIENCE IN INFORMATION TECHNOLOGY", 12, true, 120),
    titleLine("Semester III", 12, false, 60),
    titleLine("August 2026", 12, false, 0),
  ];
}

// ============================================================== content ====
const doc = [];
const add = (x) => { Array.isArray(x) ? doc.push(...x) : doc.push(x); };

add(h1("Module Description"));

add(para(
  "The system comprises thirteen functional modules. Modules M1 to M7 " +
  "implement the core grievance lifecycle. Modules M8 to M13 extend the " +
  "system with administration, escalation, duplicate handling, self service, " +
  "announcements and performance measurement. Each module is described below " +
  "with its purpose, the functions it provides, its inputs and outputs, and " +
  "the business rules it enforces."));

add(table("Module summary",
  ["Code", "Module", "Primary user", "Routes", "Tables used"],
  [
    ["M1", "Authentication and Access Control", "All", "7", "users"],
    ["M2", "Complaint Submission", "Student", "1",
     "complaints, categories, history"],
    ["M3", "Complaint Tracking and Interaction", "Student", "5",
     "complaints, history, comments, feedback"],
    ["M4", "Assignment and Auto Routing", "Administrator", "1",
     "complaints, departments, users"],
    ["M5", "Complaint Processing", "Staff", "2", "complaints, history"],
    ["M6", "Notification and Live Update", "All", "3", "notifications"],
    ["M7", "Analytics and Reporting", "Administrator", "5",
     "complaints, categories, departments, feedback"],
    ["M8", "Administration Console and Master Data", "Administrator", "9",
     "users, departments, categories"],
    ["M9", "Escalation and Reminder Engine", "Administrator", "3",
     "escalations, complaints, notifications"],
    ["M10", "Duplicate Detection and Grouping", "Student, Administrator", "4",
     "complaint_links, complaint_supporters"],
    ["M11", "Knowledge Base and Self Service", "Student", "5", "kb_articles"],
    ["M12", "Announcements and Notice Board", "Administrator", "4",
     "announcements"],
    ["M13", "Staff Performance Scorecard", "Administrator", "2",
     "complaints, feedback, users"],
  ],
  [0.07, 0.31, 0.19, 0.09, 0.34], ["C", "L", "L", "C", "L"]));

add(table("Scale of the module set",
  ["Measure", "Core (M1 to M7)", "Extension (M8 to M13)", "Total"],
  [
    ["Modules", "7", "6", "13"],
    ["Application routes", "24", "27", "51"],
    ["Database tables", "8", "5 additional", "13"],
    ["Documented algorithms", "3", "3", "6"],
  ],
  [0.34, 0.22, 0.24, 0.20], ["L", "C", "C", "C"]));

// -- M1 ----------------------------------------------------------------------
add(h1("1.  Module M1 - Authentication and Access Control"));

add(h2("Purpose"));
add(para(
  "Establishes identity, maintains the session, and guarantees that each user " +
  "reaches only the areas and records to which they are entitled."));

add(h2("Functions provided"));
add(table("Functions of module M1",
  ["Function", "Route", "Description"],
  [
    ["Landing page", "/",
     "Public entry point. Shows headline counts and redirects an already " +
     "authenticated user to their own dashboard."],
    ["Registration", "/register",
     "Self service student sign up. Validates name length, mail address " +
     "format, minimum password length and password confirmation, and rejects " +
     "an address already present in the users table."],
    ["Login", "/login",
     "Verifies the submitted password against the stored hash and establishes " +
     "a session."],
    ["Role redirect", "/home",
     "A single decision point that sends each role to its own landing page, " +
     "so no other route needs to repeat that logic."],
    ["Logout", "/logout", "Terminates the session."],
    ["Forgot password", "/forgot",
     "Issues a 32 byte URL safe token with a one hour expiry and stores it " +
     "against the user record."],
    ["Reset password", "/reset/token",
     "Validates the token and its expiry, then replaces the password hash and " +
     "clears the token so that it cannot be reused."],
  ],
  [0.19, 0.19, 0.62]));

add(h2("Business rules enforced"));
add(bullets([
  "Passwords are never stored in plain text. They are hashed with Werkzeug on " +
  "registration and on reset, and only ever compared as hashes.",
  "A failed login returns a single generic message regardless of whether the " +
  "mail address exists, so the form cannot be used to enumerate registered " +
  "accounts.",
  "The forgot password page returns the same acknowledgement for a registered " +
  "and an unregistered address, for the same reason.",
  "A reset token is single use and expires after one hour.",
  "A deactivated account cannot log in even with correct credentials.",
  "The role_required decorator is applied to every route that is not public.",
]));

add(h2("Authorisation model"));
add(table("Permissions by role",
  ["Role", "May view", "May modify"],
  [
    ["Student", "Only complaints they raised",
     "Own complaints: add comment, submit rating, reopen"],
    ["Staff", "Complaints assigned to them or routed to their department",
     "Assigned complaints: update status with remark, add comment"],
    ["Administrator", "All complaints and all analytics",
     "Assign or reassign any complaint, update any status"],
  ],
  [0.17, 0.40, 0.43]));
add(para(
  "Role checks alone are insufficient. A student holds the correct role for " +
  "the tracking page, but must not open another student's ticket. The " +
  "application therefore performs a second, record level ownership check " +
  "through can_view on every route that addresses a specific complaint."));

// -- M2 ----------------------------------------------------------------------
add(h1("2.  Module M2 - Complaint Submission"));

add(h2("Purpose"));
add(para(
  "Captures a new grievance and establishes every derived value on which the " +
  "rest of the system depends, namely the ticket code, the resolution " +
  "deadline and the initial priority score."));

add(h2("Input fields"));
add(table("Submission form fields and validation",
  ["Field", "Type", "Validation"],
  [
    ["Category", "Dropdown, required", "Must match an existing category row"],
    ["Subject", "Text, required", "Minimum 5 characters, maximum 200"],
    ["Description", "Textarea, required", "Minimum 15 characters"],
    ["Attachment", "File, optional",
     "Extension must be png, jpg, jpeg, gif, pdf or docx, maximum 5 MB"],
    ["Anonymous", "Checkbox, optional",
     "When set, staff and administrator views display Anonymous in place of " +
     "the student name"],
  ],
  [0.17, 0.20, 0.63]));

add(h2("Processing sequence"));
add(numbers([
  "Validate all fields and collect every error before responding, so that the " +
  "user is not corrected one field at a time.",
  "Validate and store the attachment if one is present. The stored filename " +
  "is prefixed with twelve random hexadecimal characters, so two users " +
  "uploading a file of the same name cannot overwrite one another.",
  "Read sla_days from the selected category and compute the deadline as the " +
  "submission time plus that many days.",
  "Compute the initial priority score from the category weight.",
  "Insert the complaint row, then derive the ticket code from the assigned " +
  "row identifier and write it back, which guarantees that the code and the " +
  "record always correspond.",
  "Write the first audit row with a null previous status and the new status " +
  "Pending.",
  "Insert a notification for every administrator.",
]));

add(h2("Ticket code format"));
add(mono([
  "GRV - <four digit year> - <four digit sequence>",
  "",
  "Example:  GRV-2026-0031",
]));

// -- M3 ----------------------------------------------------------------------
add(h1("3.  Module M3 - Complaint Tracking and Interaction"));

add(h2("Purpose"));
add(para(
  "Gives the student continuous visibility of their complaint and the means " +
  "to interact with it after submission."));

add(h2("Functions provided"));
add(table("Functions of module M3",
  ["Function", "Route", "Description"],
  [
    ["Dashboard", "/student",
     "All complaints raised by the logged in student, rendered as responsive " +
     "cards with status badges and SLA state, together with four summary tiles."],
    ["Track", "/complaint/code",
     "Full detail, attachment link, vertical status timeline built from the " +
     "audit table, comment thread, and the rating or reopen controls where " +
     "applicable."],
    ["Comment", "/complaint/id/comment",
     "Appends a message to the thread and notifies the other party, never the " +
     "author."],
    ["Feedback", "/complaint/id/feedback",
     "Records a rating of 1 to 5 with an optional remark."],
    ["Reopen", "/complaint/id/reopen",
     "Returns a completed complaint to active handling."],
  ],
  [0.16, 0.25, 0.59]));

add(h2("Conditional interface rules"));
add(bullets([
  "The rating form is rendered only when the status is Resolved or Closed, " +
  "and only for the student who raised the complaint. The server rechecks " +
  "both conditions on submission, so hiding the form is a convenience rather " +
  "than the security control.",
  "A rating may be submitted only once per complaint, which is enforced by a " +
  "unique constraint on complaint_id in the feedback table.",
  "Submitting a rating transitions the complaint to Closed and records that " +
  "transition in the audit table.",
  "The reopen control appears only for a complaint in the Resolved, Closed or " +
  "Rejected state.",
  "Reopening increments reopen_count, clears resolved_at, recalculates the " +
  "deadline from the reopen moment, and raises the priority score.",
]));

// -- M4 ----------------------------------------------------------------------
add(h1("4.  Module M4 - Assignment and Auto Routing"));

add(h2("Purpose"));
add(para(
  "Determines which department is responsible for a complaint and which " +
  "member of staff will act on it."));

add(h2("Auto routing mechanism"));
add(para(
  "Each department carries a keyword vocabulary. When the administrator opens " +
  "the assignment screen, the complaint subject and description are scanned " +
  "against every vocabulary and each department receives a score. A keyword " +
  "found in the subject contributes three points; the same keyword found in " +
  "the description contributes one point. The department with the highest " +
  "total is presented as the suggestion."));
add(mono([
  "for each department:",
  "    score = 0",
  "    for each keyword in that department's vocabulary:",
  "        if whole-word match in subject:      score += 3",
  "        if whole-word match in description:  score += 1",
  "",
  "suggestion = department with the highest score",
  "if every score is zero: no suggestion is offered",
]));
add(para(
  "Matching uses whole word boundaries rather than substring matching. " +
  "Without that constraint the keyword ac, standing for air conditioning, " +
  "would match inside the word academics and route maintenance complaints to " +
  "the academic office."));
add(para(
  "When no keyword matches at all, the system deliberately offers no " +
  "suggestion and asks the administrator to choose. Presenting a confident " +
  "but arbitrary guess is worse than presenting none, because an " +
  "administrator working quickly will accept it."));

add(h2("Assignment support"));
add(bullets([
  "The staff dropdown displays each member's current open complaint count, so " +
  "that work can be distributed rather than concentrated.",
  "Selecting a department filters the staff list to that department's members.",
  "Assignment sets the department, the assignee and the status Assigned, " +
  "writes an audit row naming the assignee, and notifies both the assigned " +
  "member of staff and the student.",
]));
add(para(
  "This is a rule based classifier and not machine learning. That is a " +
  "considered choice. Its decisions can be explained line by line, it " +
  "requires no training data, it cannot degrade unpredictably, and the " +
  "keyword lists can be tuned by non programmers as institutional vocabulary " +
  "changes. For a fixed set of departments and a stable problem domain it is " +
  "the appropriate tool."));

// -- M5 ----------------------------------------------------------------------
add(h1("5.  Module M5 - Complaint Processing"));

add(h2("Purpose"));
add(para(
  "Provides staff with their work queue and the means to advance a complaint " +
  "through the workflow."));

add(h2("Status vocabulary"));
add(table("Complaint statuses",
  ["Status", "Meaning", "Set by"],
  [
    ["Pending", "Submitted, not yet assigned", "System on submission"],
    ["Assigned", "Allocated to a member of staff", "Administrator"],
    ["In Progress", "Actively being worked", "Staff"],
    ["Resolved", "Work complete, awaiting confirmation", "Staff"],
    ["Closed", "Confirmed complete", "Student rating, or staff"],
    ["Reopened", "Returned to handling after resolution", "Student"],
    ["Rejected", "Outside scope or not reproducible", "Staff"],
  ],
  [0.18, 0.52, 0.30]));

add(h2("Processing rules"));
add(bullets([
  "The staff queue is sorted by live priority score in descending order, so " +
  "the most urgent complaint is always presented first.",
  "A remark is mandatory on every status change. The remark is displayed to " +
  "the student on the timeline and forms the permanent record of what was done.",
  "Every change writes an audit row capturing the previous status, the new " +
  "status, the remark, the responsible user and the timestamp.",
  "Transitions to Resolved or Closed set resolved_at, which is the " +
  "measurement point for the average resolution time analytic.",
  "The student is notified on every change.",
]));

// -- M6 ----------------------------------------------------------------------
add(h1("6.  Module M6 - Notification and Live Update"));

add(h2("Purpose"));
add(para(
  "Delivers state changes to the user without requiring a page reload."));

add(h2("Endpoints and clients"));
add(table("Live update endpoints",
  ["Endpoint", "Client", "Interval", "Behaviour"],
  [
    ["/api/complaint/code/status", "track.js", "5 seconds",
     "Returns the current status, colour, deadline, breach flag, days " +
     "remaining and the audit row count."],
    ["/api/notifications", "notify.js", "15 seconds",
     "Returns the ten most recent notifications and the unread count."],
    ["/api/notifications/read", "notify.js", "On demand",
     "Marks all of the user's notifications as read."],
  ],
  [0.28, 0.14, 0.14, 0.44]));

add(h2("Update strategy"));
add(para(
  "The tracking client updates the status badge, the deadline and the SLA " +
  "line in place. It does not attempt to rebuild the timeline in JavaScript. " +
  "Instead it compares the audit row count returned by the interface against " +
  "the count present when the page was rendered, and when the server count is " +
  "higher the page is reloaded once so that the server rebuilds the timeline."));
add(para(
  "This avoids maintaining two independent renderings of the same data, one " +
  "in Jinja and one in JavaScript, which would inevitably diverge. The " +
  "frequent and inexpensive update is handled on the client, while the rare " +
  "and complex update is delegated back to the server."));

add(h2("Security of client rendering"));
add(para(
  "Notification text incorporates complaint subjects, which are user input. " +
  "Before insertion into the document the client assigns the text to a " +
  "textContent property and reads back the escaped innerHTML, so that markup " +
  "contained in a subject is rendered as literal characters and cannot " +
  "execute."));

// -- M7 ----------------------------------------------------------------------
add(h1("7.  Module M7 - Analytics and Reporting"));

add(h2("Purpose"));
add(para(
  "Converts the complaint record into management information, and exports it."));

add(h2("Analytics provided"));
add(table("Analytics and their derivation",
  ["Analytic", "Method", "Presentation"],
  [
    ["Distribution by status", "GROUP BY on status",
     "Doughnut chart, with colours matched to the status badges used " +
     "throughout the interface"],
    ["Distribution by category", "LEFT JOIN with GROUP BY",
     "Horizontal bar chart, so that long category names remain readable on a " +
     "narrow screen"],
    ["Distribution by department", "LEFT JOIN with GROUP BY",
     "Vertical bar chart"],
    ["Monthly trend", "Aggregated in Python by year and month", "Line chart"],
    ["Average resolution time",
     "Difference between the submission and resolution timestamps, averaged " +
     "per department in Python",
     "Sorted table showing mean days and the number of resolved complaints " +
     "contributing"],
    ["SLA breach report", "Filtered query on status and deadline",
     "Table sorted by deadline, oldest breach first"],
    ["Top recurring issue", "Highest category count",
     "Highlighted banner identifying the largest single source of grievances"],
    ["Satisfaction", "AVG and COUNT over feedback", "Summary tiles"],
  ],
  [0.21, 0.34, 0.45]));

add(para(
  "Average resolution time and the monthly trend are both computed in Python " +
  "rather than in SQL. Both require date arithmetic. MySQL provides " +
  "TIMESTAMPDIFF and DATE_FORMAT while SQLite provides julianday and " +
  "strftime, so using either would break portability and force two versions " +
  "of the query. Performing the arithmetic in Python keeps a single " +
  "implementation that runs correctly on both engines, and the aggregation " +
  "covers resolved complaints only, so the volume is modest."));

add(h2("Search, filtering and export"));
add(bullets([
  "Filters cover free text search across ticket code, subject, description " +
  "and student name, together with status, category, department, a date range " +
  "and a breached only switch.",
  "Results are paginated at twenty per page.",
  "The Excel export writes a genuine .xlsx workbook with a styled header row, " +
  "sized columns and a frozen header pane.",
  "The PDF export renders a print optimised A4 landscape report page and uses " +
  "the browser print dialogue, which keeps the application free of additional " +
  "rendering dependencies.",
  "Both exports reuse the same filter parsing function as the list screen, so " +
  "the exported rows are exactly the rows on screen. There is no second " +
  "implementation of the filter logic that could drift.",
]));

// -- M8 ----------------------------------------------------------------------
add(h1("8.  Module M8 - Administration Console and Master Data"));

add(h2("Purpose"));
add(para(
  "Allows the administrator to manage the reference data and the user " +
  "accounts on which every other module depends, without editing source code " +
  "or reinitialising the database. Before this module existed, adding a " +
  "member of staff or a new complaint category required a developer and a " +
  "database rebuild, which destroyed all existing records."));

add(h2("Functions provided"));
add(table("Functions of module M8",
  ["Function", "Route", "Description"],
  [
    ["User list", "/admin/users",
     "All accounts with role and department, searchable by name or mail " +
     "address and filterable by role and active state."],
    ["Add user", "/admin/users/new",
     "Adds a staff or administrator account, assigns a department and sets an " +
     "initial password, which is stored only as a hash."],
    ["Edit user", "/admin/users/id/edit",
     "Changes name, mail address, telephone number, role and department."],
    ["Activate or deactivate", "/admin/users/id/toggle",
     "Suspends an account without deleting it, so the historical record of " +
     "what that user did remains intact."],
    ["Reset password", "/admin/users/id/password",
     "Sets a new password for a user who cannot access their own reset link."],
    ["Department list", "/admin/departments",
     "Lists departments with the count of complaints routed to each."],
    ["Edit department", "/admin/departments/id/edit",
     "Renames a department or changes its contact address."],
    ["Category list", "/admin/categories",
     "Lists categories with their service level in days and priority weight."],
    ["Edit category", "/admin/categories/id/edit",
     "Changes the service level, the priority weight or the owning department."],
  ],
  [0.18, 0.24, 0.58]));

add(h2("Business rules enforced"));
add(bullets([
  "An administrator cannot deactivate their own account or reduce their own " +
  "role, which prevents the last administrator from locking everyone out of " +
  "the system.",
  "A department or category that is referenced by an existing complaint " +
  "cannot be deleted. It may be renamed, so historical records keep a " +
  "meaningful label.",
  "Changing the service level of a category applies only to complaints " +
  "submitted afterwards. Existing deadlines are never rewritten, because a " +
  "deadline that moves is not a deadline.",
  "Deactivating a member of staff who holds open complaints raises a warning " +
  "listing those complaints, so that they can be reassigned first.",
  "A password set by an administrator is stored only as a hash, exactly as " +
  "one chosen by the user.",
  "Every action in this module writes to the audit record, because master " +
  "data changes affect the behaviour of the whole system.",
]));

// -- M9 ----------------------------------------------------------------------
add(h1("9.  Module M9 - Escalation and Reminder Engine"));

add(h2("Purpose"));
add(para(
  "Ensures that a complaint which is not acted upon rises through levels of " +
  "authority automatically. In every manual process the burden of chasing an " +
  "unanswered request falls on the student, which is precisely the person " +
  "least able to apply pressure. This module transfers that burden to the " +
  "system."));

add(h2("Escalation levels"));
add(para(
  "Escalation is driven by the proportion of the service level that has " +
  "elapsed, rather than by a fixed number of days, so a category with a two " +
  "day service level escalates faster than one with ten days."));
add(mono([
  "elapsed_ratio = (now - submitted_at) / (deadline - submitted_at)",
]));
add(table("Escalation levels and their triggers",
  ["Level", "Trigger", "Action taken"],
  [
    ["0  Normal", "Below 0.5", "No action"],
    ["1  Reminder", "0.5 and above",
     "Reminder notification to the assigned member of staff"],
    ["2  Department", "1.0 and above, that is past the deadline",
     "Notification to every administrator, complaint flagged as breached"],
    ["3  Management", "2.0 and above, twice the allowed time",
     "Flagged for management review and raised to maximum priority band"],
  ],
  [0.18, 0.32, 0.50]));

add(h2("Functions provided"));
add(table("Functions of module M9",
  ["Function", "Route", "Description"],
  [
    ["Escalation dashboard", "/admin/escalations",
     "Lists complaints by escalation level, oldest first, with the level " +
     "history of each."],
    ["Run sweep", "/admin/escalations/run",
     "Evaluates every open complaint, raises the level where a threshold has " +
     "been crossed and issues the corresponding notifications."],
    ["Escalation check", "/api/escalation/check",
     "Returns the count at each level, used to keep the administrator " +
     "dashboard current."],
  ],
  [0.22, 0.26, 0.52]));

add(h2("Business rules enforced"));
add(bullets([
  "A complaint may only move up a level, never down, while it remains open. " +
  "This prevents a complaint oscillating across a threshold and issuing " +
  "repeated notifications.",
  "One record is written per complaint per level, so running the sweep twice " +
  "produces no duplicate notifications. The operation is safe to repeat.",
  "Reopening a complaint resets its escalation level to zero, because the " +
  "deadline is recalculated from the reopen moment.",
  "A complaint in the Resolved, Closed or Rejected state is never escalated.",
  "Every level change is recorded with the reason and the users notified, so " +
  "the escalation history can be shown alongside the status timeline.",
]));

add(h2("Table introduced"));
add(table("Structure of the escalations table",
  ["Column", "Type", "Description"],
  [
    ["id", "INT", "Primary key"],
    ["complaint_id", "INT", "Foreign key to complaints, indexed"],
    ["from_level", "INT", "Level before the change"],
    ["to_level", "INT", "Level after the change"],
    ["reason", "TEXT", "Threshold crossed and the elapsed proportion"],
    ["notified_user_id", "INT", "Foreign key to users, nullable"],
    ["escalated_at", "DATETIME", "When the level changed"],
  ],
  [0.24, 0.18, 0.58]));

// -- M10 ---------------------------------------------------------------------
add(h1("10.  Module M10 - Duplicate Detection and Grouping"));

add(h2("Purpose"));
add(para(
  "Identifies complaints that describe the same underlying problem and allows " +
  "them to be handled as one. When a network switch fails, forty students may " +
  "each submit a separate complaint. Without this module the institution " +
  "receives forty tickets and forty separate resolution efforts, and no " +
  "indication that they are a single fault."));

add(h2("Similarity measure"));
add(para(
  "Similarity is measured between the word sets of two complaints using the " +
  "Jaccard coefficient, which is the size of the intersection divided by the " +
  "size of the union. Comparison is restricted to complaints in the same " +
  "category that are still open, which keeps the comparison inexpensive."));
add(mono([
  "A = distinct significant words of complaint one",
  "B = distinct significant words of complaint two",
  "",
  "similarity(A, B) = | A intersect B |  /  | A union B |",
  "",
  "words shorter than four characters and common words are removed",
  "a match on the subject line counts twice",
  "candidate is offered when similarity >= 0.35",
]));
add(para(
  "The Jaccard coefficient was chosen over a simple count of shared words " +
  "because a long complaint would otherwise appear similar to everything. " +
  "Dividing by the union normalises for length, so a short complaint and a " +
  "long one are compared fairly."));

add(h2("Functions provided"));
add(table("Functions of module M10",
  ["Function", "Route", "Description"],
  [
    ["Similarity check", "/api/similar",
     "Called as the student types the subject. Returns open complaints in the " +
     "same category above the similarity threshold."],
    ["Endorse an existing complaint", "/complaint/id/metoo",
     "Records the student as a supporter of an existing complaint instead of " +
     "submitting a new one."],
    ["Merge", "/complaint/id/merge",
     "Administrator links a duplicate complaint to a parent. Every supporter " +
     "of the child becomes a supporter of the parent."],
    ["Grouped view", "/complaint/id/group",
     "Shows the parent complaint together with every complaint linked to it " +
     "and the full supporter list."],
  ],
  [0.24, 0.22, 0.54]));

add(h2("Business rules enforced"));
add(bullets([
  "A student may endorse a complaint only once, which is enforced by a unique " +
  "constraint on the pair of complaint and user.",
  "A student may not endorse their own complaint.",
  "Supporter count raises the priority score, so a widely reported problem " +
  "rises in the queue. The revised score adds three points per supporter.",
  "Merging is performed by an administrator, never automatically. The " +
  "similarity measure advises; a person decides.",
  "Resolving a parent complaint resolves every complaint merged into it, and " +
  "notifies every supporter at once.",
  "A merged complaint remains visible to the student who raised it, showing " +
  "the parent it was joined to, so nobody's complaint silently disappears.",
  "Merging cannot form a chain. A complaint that is already a child cannot " +
  "become a parent.",
]));

add(h2("Revised priority score"));
add(para(
  "The priority formula defined in module M5 is extended with a supporter " +
  "term. A complaint reported by many students is genuinely more urgent than " +
  "one reported by a single student, and the score now reflects that."));
add(mono([
  "priority_score = (priority_weight  x 10)",
  "               + (days_since_submission  x  2)",
  "               + (reopen_count           x  5)",
  "               + (supporter_count        x  3)",
]));

add(h2("Tables introduced"));
add(table("Structure of the complaint_links table",
  ["Column", "Type", "Description"],
  [
    ["id", "INT", "Primary key"],
    ["parent_id", "INT", "The complaint that will be worked on"],
    ["child_id", "INT", "The duplicate, unique so it cannot be merged twice"],
    ["linked_by", "INT", "Administrator who performed the merge"],
    ["linked_at", "DATETIME", "When the merge took place"],
  ],
  [0.24, 0.18, 0.58]));
add(table("Structure of the complaint_supporters table",
  ["Column", "Type", "Description"],
  [
    ["id", "INT", "Primary key"],
    ["complaint_id", "INT", "Foreign key to complaints, indexed"],
    ["user_id", "INT", "The endorsing student"],
    ["supported_at", "DATETIME", "When the endorsement was recorded"],
  ],
  [0.24, 0.18, 0.58]));

// -- M11 ---------------------------------------------------------------------
add(h1("11.  Module M11 - Knowledge Base and Self Service"));

add(h2("Purpose"));
add(para(
  "Answers a question before it becomes a complaint. A substantial proportion " +
  "of grievances are requests for information that has already been given to " +
  "somebody else, for example the procedure for applying for revaluation. " +
  "Answering these from a searchable record costs nothing and returns an " +
  "answer immediately rather than in several days."));

add(h2("Functions provided"));
add(table("Functions of module M11",
  ["Function", "Route", "Description"],
  [
    ["Article list", "/kb",
     "Searchable list of published articles, filterable by category."],
    ["Article", "/kb/id",
     "Full article with a view counter and a helpfulness prompt."],
    ["Mark helpfulness", "/kb/id/helpful",
     "Records whether the article answered the question, which identifies " +
     "articles that need rewriting."],
    ["Manage articles", "/admin/kb",
     "Administrator list with publish and unpublish controls."],
    ["Add or edit article", "/admin/kb/save",
     "Writes an article, optionally promoted directly from the remark on a " +
     "resolved complaint."],
  ],
  [0.22, 0.20, 0.58]));

add(h2("Deflection at the point of submission"));
add(para(
  "The submission form searches the knowledge base as the student types the " +
  "subject, in the same request that checks for duplicate complaints. Matching " +
  "articles are offered above the form. If the student opens an article and " +
  "then abandons the submission, a deflection is recorded against that " +
  "article."));
add(para(
  "The deflection count is the measure of whether this module is worth " +
  "keeping. An article with many views and no deflections is not answering " +
  "the question it claims to answer."));

add(h2("Business rules enforced"));
add(bullets([
  "Only a published article is visible to students. Draft articles are " +
  "visible to the administrator alone.",
  "An article promoted from a resolved complaint carries no student " +
  "identifying information, because the resolution is general even when the " +
  "complaint was personal.",
  "A student may register helpfulness once per article.",
  "Articles are ordered by helpfulness and then by views, so the answers that " +
  "actually work are found first.",
]));

add(h2("Table introduced"));
add(table("Structure of the kb_articles table",
  ["Column", "Type", "Description"],
  [
    ["id", "INT", "Primary key"],
    ["title", "VARCHAR(200)", "Question as a student would phrase it"],
    ["body", "TEXT", "The answer"],
    ["category_id", "INT", "Foreign key to categories, nullable"],
    ["is_published", "BOOLEAN", "Draft articles are hidden from students"],
    ["views", "INT", "Number of times opened"],
    ["helpful_yes", "INT", "Positive helpfulness responses"],
    ["helpful_no", "INT", "Negative helpfulness responses"],
    ["deflections", "INT",
     "Submissions abandoned after this article was opened"],
    ["author_id", "INT", "Foreign key to users"],
    ["published_at", "DATETIME", "When it became visible"],
  ],
  [0.24, 0.18, 0.58]));

// -- M12 ---------------------------------------------------------------------
add(h1("12.  Module M12 - Announcements and Notice Board"));

add(h2("Purpose"));
add(para(
  "Informs students of a known problem before they report it. When a fault " +
  "is already known and being worked on, every further complaint about it " +
  "consumes staff attention without adding information. An announcement " +
  "shown at the point of submission removes that duplication at its source."));

add(h2("Functions provided"));
add(table("Functions of module M12",
  ["Function", "Route", "Description"],
  [
    ["Notice board", "/announcements",
     "Active announcements for the logged in user, filtered by their role and " +
     "department."],
    ["Manage announcements", "/admin/announcements",
     "Administrator list showing scheduled, active and expired entries."],
    ["Add or edit", "/admin/announcements/save",
     "Writes an announcement with an audience, a category and an active " +
     "period."],
    ["Activate or deactivate", "/admin/announcements/id/toggle",
     "Withdraws an announcement immediately without deleting the record."],
  ],
  [0.24, 0.26, 0.50]));

add(h2("Targeting and display"));
add(bullets([
  "An announcement may be addressed to all users, or to one role, or to one " +
  "department, or to a combination.",
  "An announcement carries a start and an end time and appears only within " +
  "that period, so a planned maintenance notice can be written in advance.",
  "Active announcements appear as a banner on the dashboard of every user in " +
  "the audience.",
  "An announcement may be linked to a complaint category. When a student " +
  "selects that category on the submission form, the announcement is shown " +
  "immediately with the option to abandon the submission.",
]));

add(h2("Business rules enforced"));
add(bullets([
  "An announcement whose end time has passed is retained rather than deleted, " +
  "so the record of what students were told remains available.",
  "The end time must be later than the start time.",
  "Deactivation is immediate and does not wait for the end time.",
  "Announcements are never shown to a user outside the stated audience, even " +
  "by direct link.",
]));

add(h2("Table introduced"));
add(table("Structure of the announcements table",
  ["Column", "Type", "Description"],
  [
    ["id", "INT", "Primary key"],
    ["title", "VARCHAR(200)", "Headline shown in the banner"],
    ["body", "TEXT", "Full text"],
    ["audience_role", "VARCHAR(20)",
     "all, student, staff or admin"],
    ["department_id", "INT", "Restricts to one department, nullable"],
    ["category_id", "INT",
     "Shown on the submission form for this category, nullable"],
    ["starts_at", "DATETIME", "Beginning of the display period"],
    ["ends_at", "DATETIME", "End of the display period"],
    ["is_active", "BOOLEAN", "Allows immediate withdrawal"],
    ["author_id", "INT", "Foreign key to users"],
  ],
  [0.24, 0.20, 0.56]));

// -- M13 ---------------------------------------------------------------------
add(h1("13.  Module M13 - Staff Performance Scorecard"));

add(h2("Purpose"));
add(para(
  "Measures how each member of staff and each department performs against " +
  "the service level. Module M7 reports on complaints; this module reports on " +
  "the people and offices handling them, which is the information required " +
  "for a review meeting."));

add(h2("Metrics computed"));
add(table("Performance metrics and their derivation",
  ["Metric", "Derivation", "Interpretation"],
  [
    ["Complaints handled",
     "Count of complaints ever assigned to the member of staff",
     "Volume, which gives context to every other figure"],
    ["Average resolution time",
     "Mean interval between assignment and resolution",
     "Speed. Measured from assignment rather than submission, because a " +
     "member of staff is not accountable for time before the complaint " +
     "reached them"],
    ["Service level compliance",
     "Proportion resolved on or before the deadline, as a percentage",
     "Reliability. The single most useful figure in the table"],
    ["Average satisfaction",
     "Mean student rating across their resolved complaints",
     "Quality as judged by the person who raised the complaint"],
    ["Reopen rate",
     "Reopened complaints divided by resolved complaints, as a percentage",
     "Whether work marked complete stayed complete"],
    ["Currently open", "Count of complaints not yet completed",
     "Present workload"],
    ["Currently overdue", "Open complaints past their deadline",
     "Immediate attention required"],
  ],
  [0.22, 0.36, 0.42]));

add(h2("Functions provided"));
add(table("Functions of module M13",
  ["Function", "Route", "Description"],
  [
    ["Scorecard", "/admin/performance",
     "One row per member of staff with every metric, sortable, together with " +
     "a departmental summary."],
    ["Individual detail", "/admin/performance/id",
     "The same metrics for one member of staff, with the underlying complaint " +
     "list and the rating remarks received."],
  ],
  [0.24, 0.26, 0.50]));

add(h2("Business rules and cautions"));
add(bullets([
  "All metrics are computed on read from the existing records. No aggregate " +
  "is stored, so a figure can never disagree with the underlying data.",
  "Resolution time is measured from assignment rather than from submission, " +
  "because a member of staff cannot be held responsible for the interval " +
  "before the complaint was routed to them.",
  "A member of staff with fewer than five resolved complaints is marked as " +
  "having insufficient data, because an average over two complaints is not a " +
  "measurement.",
  "Satisfaction is reported alongside volume and never on its own, since a " +
  "high average across three complaints means less than a moderate average " +
  "across sixty.",
  "The scorecard is visible to the administrator only.",
]));

// ============================================================== assemble ====
const document = new Document({
  creator: "",
  description: "",
  title: "Grievance360 Module Description",
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
      {
        reference: "number-list",
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
    ],
  },
  styles: {
    default: {
      document: {
        run: { font: FONT, size: half(BODY_PT), color: "000000" },
        paragraph: { spacing: Object.assign({ after: 160 }, LINE_15) },
      },
    },
  },
  sections: [{
    // Title page: no footer, no page number.
    properties: { page: { margin: MARGIN } },
    children: titlePage(),
  }, {
    properties: { page: { margin: MARGIN, pageNumbers: { start: 1 } } },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 120, after: 0 },
          children: [new TextRun({
            children: [PageNumber.CURRENT], font: FONT, size: half(11),
          })],
        })],
      }),
    },
    children: doc,
  }],
});

const outPath = path.join(__dirname, "Grievance360_Module_Description.docx");
Packer.toBuffer(document).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log("Written: " + outPath);
  console.log("Size:    " + (buf.length / 1024).toFixed(1) + " KB");
  console.log("Tables:  " + tableNo);
});
