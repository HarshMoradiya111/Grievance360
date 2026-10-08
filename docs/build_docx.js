/*
 * Grievance360 - project report, Word format.
 *
 * Plain academic formatting only: Times New Roman, 1.5 line spacing,
 * justified body text, built-in Word heading styles, ruled tables.
 * No graphics, no colour blocks, no decorative elements.
 *
 * Run:
 *     NODE_PATH=/c/Users/harsh/node_modules node docs/build_docx.js
 *
 * NODE_PATH is needed only because the docx package is installed globally
 * rather than in this project. If you run "npm install docx" here first,
 * plain "node docs/build_docx.js" works.
 */

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, WidthType, BorderStyle, ShadingType,
  TableOfContents, PageBreak, PageNumber, Footer, LevelFormat,
  VerticalAlign, TabStopType, convertInchesToTwip,
} = require("docx");

// --------------------------------------------------------------- layout ----
const FONT = "Times New Roman";
const MONO = "Courier New";
const BODY_PT = 12;
const TABLE_PT = 10.5;

// A4 = 11906 x 16838 twips. Left margin is wider to allow for binding.
const MARGIN = { top: 1440, bottom: 1440, left: 1800, right: 1440 };
const CONTENT_W = 11906 - MARGIN.left - MARGIN.right;   // 8666 twips

const half = (pt) => pt * 2;          // Word sizes are in half-points
const LINE_15 = { line: 360, lineRule: "auto" };

let listInstance = 0;

// ---------------------------------------------------------------- blocks ----
function para(text, opts = {}) {
  return new Paragraph({
    alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: Object.assign({ after: 160 }, LINE_15, opts.spacing || {}),
    indent: opts.indent,
    keepNext: opts.keepNext || false,
    children: [new TextRun({
      text: text,
      font: opts.font || FONT,
      size: half(opts.size || BODY_PT),
      bold: opts.bold || false,
      italics: opts.italics || false,
    })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    pageBreakBefore: true,
    spacing: { before: 0, after: 240, line: 300, lineRule: "auto" },
    children: [new TextRun({ text, font: FONT, size: half(15), bold: true,
                             color: "000000" })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 320, after: 160, line: 300, lineRule: "auto" },
    keepNext: true,
    children: [new TextRun({ text, font: FONT, size: half(13), bold: true,
                             color: "000000" })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
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

/* A monospaced, indented block for formulas and directory listings. */
function mono(lines) {
  return lines.map((l, i) => new Paragraph({
    alignment: AlignmentType.LEFT,
    indent: { left: 480 },
    spacing: { after: i === lines.length - 1 ? 200 : 0, line: 260,
               lineRule: "auto" },
    // Hold the block together so a formula is never split across two pages.
    keepNext: i < lines.length - 1,
    keepLines: true,
    children: [new TextRun({ text: l || " ", font: MONO, size: half(10) })],
  }));
}

/* A caption line above a table, as in a printed report. */
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.LEFT,
    spacing: { before: 160, after: 100 },
    keepNext: true,
    children: [new TextRun({ text, font: FONT, size: half(11), bold: true })],
  });
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
        text: String(text),
        font: FONT,
        size: half(TABLE_PT),
        bold: opts.head || false,
      })],
    })],
  });
}

/*
 * Build a ruled table. `fractions` are proportions of the text width, so
 * every table lines up with the left and right edge of the body text.
 */
function table(headers, rows, fractions, aligns) {
  const total = fractions.reduce((a, b) => a + b, 0);
  const widths = fractions.map((f) => Math.round((f / total) * CONTENT_W));
  const drift = CONTENT_W - widths.reduce((a, b) => a + b, 0);
  widths[widths.length - 1] += drift;          // absorb rounding error

  const alignOf = (i) =>
    aligns && aligns[i] === "C" ? AlignmentType.CENTER : AlignmentType.LEFT;

  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((t, i) =>
      cell(t, widths[i], { head: true, align: alignOf(i) })),
  });

  const bodyRows = rows.map((r) => new TableRow({
    children: r.map((t, i) => cell(t, widths[i], { align: alignOf(i) })),
  }));

  return [
    new Table({
      columnWidths: widths,
      width: { size: CONTENT_W, type: WidthType.DXA },
      rows: [headRow].concat(bodyRows),
    }),
    new Paragraph({ spacing: { after: 200 }, children: [] }),
  ];
}

// ------------------------------------------------------------ title page ----
function titleLine(text, size, bold, spaceAfter, italics) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: spaceAfter === undefined ? 200 : spaceAfter,
               line: 300, lineRule: "auto" },
    children: [new TextRun({
      text, font: FONT, size: half(size), bold: !!bold, italics: !!italics,
    })],
  });
}

function titlePage() {
  return [
    titleLine("GRIEVANCE360", 26, true, 160),
    titleLine("A Smart Grievance Redressal and Analytics Portal", 14, false, 40),
    titleLine("for Educational Institutions", 14, false, 700),

    titleLine("A PROJECT REPORT", 15, true, 500),

    titleLine("Submitted in partial fulfilment of the requirements", 12,
              false, 40),
    titleLine("for the award of the degree of", 12, false, 300),

    titleLine("MASTER OF SCIENCE", 14, true, 40),
    titleLine("IN", 12, false, 40),
    titleLine("INFORMATION TECHNOLOGY", 14, true, 700),

    titleLine("Submitted by", 12, false, 240),
    titleLine("25MSIT077", 13, true, 80),
    titleLine("25MSIT166", 13, true, 80),
    titleLine("25MSIT134", 13, true, 900),

    titleLine("Semester III", 12, false, 60),
    titleLine("August 2026", 12, false, 0),
  ];
}

// ============================================================== content ====
const doc = [];
const add = (x) => { Array.isArray(x) ? doc.push(...x) : doc.push(x); };

// ---- Contents --------------------------------------------------------------
add(new Paragraph({
  alignment: AlignmentType.CENTER,
  pageBreakBefore: true,
  spacing: { after: 320, line: 300, lineRule: "auto" },
  children: [new TextRun({ text: "CONTENTS", font: FONT, size: half(15),
                           bold: true })],
}));
add(new TableOfContents("Contents", {
  hyperlink: true,
  headingStyleRange: "1-3",
}));

// ---- 1. Introduction -------------------------------------------------------
add(h1("1.  Introduction"));

add(h2("1.1  Problem statement"));
add(para(
  "In most educational institutions a grievance is raised on paper, in a " +
  "register at a departmental office, or verbally to a member of staff. Once " +
  "submitted, the complaint effectively disappears. The student has no " +
  "reference number, no way to check progress, and no evidence that the " +
  "complaint was ever recorded. The administration has no consolidated view " +
  "either, so recurring problems are never identified, no department is held " +
  "to a resolution deadline, and the same issue is reported repeatedly " +
  "without anyone noticing the pattern."));
add(para(
  "The absence of an audit trail is the central weakness. Without a record of " +
  "who changed what and when, accountability cannot be established, and " +
  "without measurable deadlines no service standard can be enforced."));

add(h2("1.2  Proposed solution"));
add(para(
  "Grievance360 is a web application that digitises the complete grievance " +
  "lifecycle. A student submits a complaint from a mobile phone and " +
  "immediately receives a unique ticket code. The system reads the complaint " +
  "text and suggests the responsible department automatically. An " +
  "administrator assigns it to a member of staff, who works it through a " +
  "defined sequence of statuses. Every status change is written to an audit " +
  "table together with the remark and the identity of the person who made it."));
add(para(
  "The student watches this progress on a live timeline that refreshes itself " +
  "without a page reload. When the complaint is resolved the student rates " +
  "the response, and if the problem returns the complaint can be reopened in " +
  "one tap. The administration sees the whole picture through an analytics " +
  "dashboard covering complaint distribution, average resolution time per " +
  "department, a service level breach report and the single largest recurring " +
  "issue."));

add(h2("1.3  Significance of the name"));
add(para(
  "Grievance360 refers to the complete circle a grievance travels: raised, " +
  "routed, assigned, worked, resolved, rated and, where necessary, reopened. " +
  "The system closes that loop, and it also offers a 360 degree view of the " +
  "data to the administration through analytics."));

add(h2("1.4  Scope of this document"));
add(para(
  "This report documents the delivered system. It specifies the seven " +
  "functional modules, the database design, the two core algorithms, the " +
  "security measures applied and the quality assurance carried out. All test " +
  "results reported in Chapter 10 were obtained by executing the application " +
  "rather than by inspection of the source code."));

// ---- 2. Objectives ---------------------------------------------------------
add(h1("2.  Objectives and Scope"));

add(h2("2.1  Primary objectives"));
add(numbers([
  "Provide students with a mobile first interface for submitting a grievance " +
  "in under one minute, with an optional file attachment and an option to " +
  "remain anonymous.",
  "Issue a unique, human readable ticket code for every complaint so that it " +
  "can be referenced and tracked.",
  "Maintain an immutable audit trail of every status change, capturing the " +
  "previous status, the new status, an explanatory remark, the user " +
  "responsible and the timestamp.",
  "Route complaints to the correct department automatically by analysing the " +
  "complaint text, while leaving the final decision with the administrator.",
  "Enforce a service level agreement by attaching a resolution deadline to " +
  "every complaint and reporting breaches prominently.",
  "Rank the pending queue by an objective priority score rather than by " +
  "submission date alone.",
  "Deliver status changes to the user without a page reload.",
  "Present the administration with analytics covering distribution, average " +
  "resolution time, breach volume and the top recurring issue, and allow any " +
  "filtered view to be exported.",
]));

add(h2("2.2  In scope"));
add(bullets([
  "Three user roles, namely student, staff and administrator, with strict " +
  "role based access control and per record ownership checks.",
  "Self service student registration. Staff and administrator accounts are " +
  "provisioned by the administrator.",
  "Password reset using a single use, time limited token.",
  "Complete complaint lifecycle across seven statuses.",
  "File attachments restricted by type and size.",
  "Two way comment thread between the student and the assigned member of staff.",
  "Star rating captured after resolution, and a reopen path.",
  "Notification records with a live unread counter.",
  "Search, multi field filtering and pagination over all complaints.",
  "Excel and PDF export of the currently filtered view.",
]));

add(h2("2.3  Out of scope"));
add(bullets([
  "Electronic mail and SMS delivery. No mail server is available in the " +
  "college laboratory, so the password reset link is displayed on screen " +
  "instead of being sent by mail. The token issue, expiry and single use " +
  "logic are identical to a production mail flow; only the delivery channel " +
  "differs.",
  "Native mobile applications. The web interface is mobile first and the " +
  "installed browser is the delivery mechanism.",
  "Integration with an existing institutional ERP or student information " +
  "system.",
  "Multi institution tenancy. The system is designed for one institution.",
]));

add(h2("2.4  Assumptions"));
add(bullets([
  "Students access the system predominantly from mobile phones. The design " +
  "assumes a 98 percent mobile and 2 percent desktop split, which is why the " +
  "interface is built phone first rather than adapted downwards from a " +
  "desktop layout.",
  "Each department has at least one member of staff who can act on assigned " +
  "complaints.",
  "Complaint volume is at institutional scale, that is thousands of records " +
  "rather than millions, which is why polling is an acceptable live update " +
  "mechanism.",
]));

// ---- 3. Technology stack ---------------------------------------------------
add(h1("3.  Technology Stack"));

add(h2("3.1  Components and justification"));
add(caption("Table 3.1  Technology selection"));
add(table(
  ["Layer", "Technology", "Reason for selection"],
  [
    ["Language", "Python 3",
     "Readable syntax suits a documented academic project, and the extensive " +
     "standard library reduces third party dependencies."],
    ["Web framework", "Flask 3.1",
     "Minimal and explicit. Every route, query and template is visible in the " +
     "source rather than hidden behind framework conventions, which matters " +
     "when the code must be explained during assessment."],
    ["Database", "SQLite 3 and MySQL 8",
     "MySQL is the target platform and holds the canonical schema. SQLite is " +
     "the development default so the project runs with no server installation."],
    ["Database driver", "PyMySQL 1.1",
     "A pure Python implementation of the MySQL wire protocol. It installs on " +
     "any Python version without a C compiler, unlike mysqlclient which " +
     "requires Visual Studio build tools on Windows."],
    ["Authentication", "Flask-Login 0.6",
     "Provides session management and the user loader, combined with a custom " +
     "role decorator for authorisation."],
    ["Password hashing", "Werkzeug 3.1",
     "Salted PBKDF2 hashing through generate_password_hash and " +
     "check_password_hash."],
    ["Templating", "Jinja2",
     "Ships with Flask. Auto escaping is enabled by default, which " +
     "neutralises cross site scripting in rendered output."],
    ["Front end framework", "Bootstrap 5.3",
     "A mature responsive grid and component set delivered by CDN, which " +
     "removes the need to hand write breakpoint logic."],
    ["Client scripting", "Vanilla JavaScript",
     "No front end build step and no framework to learn or explain. Three " +
     "small self contained files using the fetch API."],
    ["Charting", "Chart.js 4.4",
     "Responsive canvas charts with a small API surface."],
    ["Spreadsheet export", "openpyxl 3.1",
     "Writes a genuine .xlsx workbook with styled headers and frozen panes."],
  ],
  [0.16, 0.20, 0.64]));

add(h2("3.2  Database portability design"));
add(para(
  "The application must demonstrate MySQL for assessment purposes but also " +
  "run on any laboratory machine without a database server installed. Rather " +
  "than maintaining two versions of the code, the project uses a single set " +
  "of queries together with a compatibility shim."));
add(para(
  "Every SQL statement in the codebase is written in MySQL style using the " +
  "percent-s placeholder. When the SQLite engine is selected, a four line " +
  "cursor wrapper in db.py rewrites those placeholders into the question " +
  "marks that SQLite expects, and converts result rows into dictionaries so " +
  "that the templates behave identically. Engine specific functions such as " +
  "NOW, DATE_ADD and TIMESTAMPDIFF are never used; all date arithmetic is " +
  "performed in Python and passed in as parameters."));
add(mono([
  "def execute(self, sql, params=()):",
  "    # MySQL uses %s, SQLite uses ?. Rewrite at the driver",
  "    # boundary so that no query in the project has to change.",
  "    return self._cursor.execute(sql.replace('%s', '?'), params)",
]));
add(para(
  "The outcome of this design is that switching the entire application from " +
  "SQLite to MySQL requires editing exactly one line, namely DB_ENGINE in " +
  "config.py, and changing no queries at all. Because no query is edited, no " +
  "query can regress during the switch. This is the practical benefit of " +
  "isolating dialect differences at a single boundary rather than scattering " +
  "conditional statements through the data access code."));

// ---- 4. Architecture -------------------------------------------------------
add(h1("4.  System Architecture"));

add(h2("4.1  Architectural pattern"));
add(para(
  "The application follows a layered architecture. Each layer has one " +
  "responsibility and depends only on the layer beneath it, so a change in " +
  "presentation cannot affect the business rules and a change of database " +
  "engine cannot affect either."));
add(caption("Table 4.1  Responsibility of each layer"));
add(table(
  ["Layer", "Files", "Responsibility"],
  [
    ["Presentation", "templates, static",
     "Renders HTML through Jinja2 templates that all extend a single " +
     "responsive base layout. Client scripts handle live polling only."],
    ["Routing and control", "app.py",
     "Receives requests, enforces authentication and authorisation, validates " +
     "input, orchestrates calls to the layers below and selects a template or " +
     "a JSON response."],
    ["Business logic", "helpers.py",
     "Priority scoring, SLA breach evaluation, auto routing, ticket code " +
     "assignment, date handling and upload validation. Contains no SQL and no " +
     "HTTP."],
    ["Data access", "db.py",
     "Connection management, the placeholder compatibility shim and four " +
     "query helpers. The only file that knows which engine is in use."],
    ["Configuration", "config.py",
     "Engine selection, credentials, upload rules, status vocabulary and page " +
     "size. Contains no logic."],
    ["Persistence", "database folder",
     "Schema definitions for both engines, initialisation and demonstration " +
     "data scripts."],
  ],
  [0.17, 0.18, 0.65]));

add(h2("4.2  Request lifecycle"));
add(para(
  "The sequence below traces a single authenticated request from the browser " +
  "to the response. Every route follows the same path."));
add(numbers([
  "The browser issues an HTTP request carrying the session cookie.",
  "Flask-Login resolves the cookie to a user record through the registered " +
  "user loader, populating current_user.",
  "The login_required decorator confirms that a user is authenticated. An " +
  "anonymous request is redirected to the login page.",
  "The role_required decorator confirms that the user holds one of the roles " +
  "permitted for that route. A mismatch is redirected with an error message " +
  "rather than a bare HTTP 403 response.",
  "For routes addressing a specific complaint, can_view performs an ownership " +
  "check so that a user of the correct role still cannot open another " +
  "person's record.",
  "The route validates the submitted input and collects error messages.",
  "The route calls helpers for any business decision and database helpers for " +
  "persistence. A connection is opened once per request and closed " +
  "automatically by the registered teardown handler.",
  "Status changing routes write an audit row and insert notification records " +
  "for the affected parties.",
  "The route renders a Jinja2 template or returns a JSON payload.",
]));

add(h2("4.3  Template inheritance"));
add(para(
  "Every page in the application extends the base template. The base template " +
  "owns the viewport declaration, the Bootstrap and stylesheet links, the " +
  "responsive navigation bar, the notification bell, the flash message " +
  "region, the mobile bottom navigation and the footer. Feature pages supply " +
  "only a content block."));
add(para(
  "This single decision is what keeps the interface consistent. " +
  "Responsiveness is solved once in the parent and inherited by every child, " +
  "so a new page cannot accidentally be non responsive, and a layout " +
  "correction applies everywhere simultaneously. Repeated components such as " +
  "the complaint card are defined once as Jinja macros and imported where " +
  "needed, for the same reason."));

// ---- 5. Modules ------------------------------------------------------------
add(h1("5.  Module Description"));
add(para(
  "The system comprises seven functional modules. Each is described below " +
  "with its purpose, the functions it provides, its inputs and outputs, and " +
  "the business rules it enforces."));
add(caption("Table 5.1  Module summary"));
add(table(
  ["Code", "Module", "Primary user", "Routes"],
  [
    ["M1", "Authentication and Access Control", "All", "6"],
    ["M2", "Complaint Submission", "Student", "1"],
    ["M3", "Complaint Tracking and Interaction", "Student", "4"],
    ["M4", "Assignment and Auto Routing", "Administrator", "1"],
    ["M5", "Complaint Processing", "Staff", "2"],
    ["M6", "Notification and Live Update", "All", "3"],
    ["M7", "Analytics and Reporting", "Administrator", "5"],
  ],
  [0.09, 0.45, 0.26, 0.12], ["C", "L", "L", "C"]));

add(h2("5.1  Module M1 - Authentication and Access Control"));
add(h3("Purpose"));
add(para(
  "Establishes identity, maintains the session, and guarantees that each user " +
  "reaches only the areas and records to which they are entitled."));
add(h3("Functions provided"));
add(caption("Table 5.2  Functions of module M1"));
add(table(
  ["Function", "Route", "Description"],
  [
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

add(h3("Business rules enforced"));
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

add(h3("Authorisation model"));
add(caption("Table 5.3  Permissions by role"));
add(table(
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
  "through can_view on every route that addresses a specific complaint. Test " +
  "case 45 in Chapter 10 verifies this behaviour directly."));

add(h2("5.2  Module M2 - Complaint Submission"));
add(h3("Purpose"));
add(para(
  "Captures a new grievance and establishes every derived value on which the " +
  "rest of the system depends, namely the ticket code, the resolution " +
  "deadline and the initial priority score."));
add(h3("Input fields"));
add(caption("Table 5.4  Submission form fields and validation"));
add(table(
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

add(h3("Processing sequence"));
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
add(h3("Ticket code format"));
add(mono([
  "GRV - <four digit year> - <four digit sequence>",
  "",
  "Example:  GRV-2026-0031",
]));

add(h2("5.3  Module M3 - Complaint Tracking and Interaction"));
add(h3("Purpose"));
add(para(
  "Gives the student continuous visibility of their complaint and the means " +
  "to interact with it after submission."));
add(h3("Functions provided"));
add(caption("Table 5.5  Functions of module M3"));
add(table(
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

add(h3("Conditional interface rules"));
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

add(h2("5.4  Module M4 - Assignment and Auto Routing"));
add(h3("Purpose"));
add(para(
  "Determines which department is responsible for a complaint and which " +
  "member of staff will act on it."));
add(h3("Auto routing mechanism"));
add(para(
  "Each department carries a keyword vocabulary. When the administrator opens " +
  "the assignment screen, the complaint subject and description are scanned " +
  "against every vocabulary and each department receives a score. A keyword " +
  "found in the subject contributes three points; the same keyword found in " +
  "the description contributes one point. The department with the highest " +
  "total is presented as the suggestion."));
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
add(h3("Assignment support"));
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

add(h2("5.5  Module M5 - Complaint Processing"));
add(h3("Purpose"));
add(para(
  "Provides staff with their work queue and the means to advance a complaint " +
  "through the workflow."));
add(h3("Status vocabulary"));
add(caption("Table 5.6  Complaint statuses"));
add(table(
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
add(h3("Processing rules"));
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

add(h2("5.6  Module M6 - Notification and Live Update"));
add(h3("Purpose"));
add(para(
  "Delivers state changes to the user without requiring a page reload."));
add(h3("Endpoints and clients"));
add(caption("Table 5.7  Live update endpoints"));
add(table(
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

add(h3("Update strategy"));
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
add(h3("Security of client rendering"));
add(para(
  "Notification text incorporates complaint subjects, which are user input. " +
  "Before insertion into the document the client assigns the text to a " +
  "textContent property and reads back the escaped innerHTML, so that markup " +
  "contained in a subject is rendered as literal characters and cannot " +
  "execute."));

add(h2("5.7  Module M7 - Analytics and Reporting"));
add(h3("Purpose"));
add(para(
  "Converts the complaint record into management information, and exports it."));
add(h3("Analytics provided"));
add(caption("Table 5.8  Analytics and their derivation"));
add(table(
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
     "Difference between created_at and resolved_at, averaged per department " +
     "in Python",
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

add(h3("Search, filtering and export"));
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

// ---- 6. Database -----------------------------------------------------------
add(h1("6.  Database Design"));

add(h2("6.1  Entity overview"));
add(para(
  "The schema comprises eight tables. Users of all three roles are held in a " +
  "single table separated by a role column, which keeps authentication " +
  "uniform and allows a foreign key from a complaint to point at either the " +
  "student who raised it or the member of staff handling it."));
add(caption("Table 6.1  Tables and relationships"));
add(table(
  ["No.", "Table", "Purpose", "Key relationships"],
  [
    ["1", "departments", "Offices that resolve complaints",
     "Referenced by categories, users, complaints"],
    ["2", "categories",
     "Complaint types, each carrying its own SLA and urgency weight",
     "References departments"],
    ["3", "users", "Students, staff and administrators",
     "References departments"],
    ["4", "complaints", "The central record",
     "References users, categories, departments"],
    ["5", "complaint_status_history", "Audit trail of every status change",
     "References complaints, users"],
    ["6", "comments", "Student and staff conversation",
     "References complaints, users"],
    ["7", "feedback", "Star rating, one per complaint",
     "References complaints, users"],
    ["8", "notifications", "Feeds the live unread counter",
     "References users, complaints"],
  ],
  [0.06, 0.24, 0.38, 0.32], ["C", "L", "L", "L"]));

add(h2("6.2  Data dictionary for the complaints table"));
add(para(
  "The complaints table is the centre of the schema and is documented in full " +
  "below."));
add(caption("Table 6.2  Data dictionary, complaints"));
add(table(
  ["Column", "Type", "Constraint", "Description"],
  [
    ["id", "INT", "Primary key",
     "Surrogate key, and the source of the ticket sequence"],
    ["ticket_code", "VARCHAR(20)", "Unique, indexed",
     "Human readable reference in the form GRV-YYYY-NNNN"],
    ["user_id", "INT", "Foreign key, indexed",
     "The student who raised the complaint"],
    ["category_id", "INT", "Foreign key, indexed",
     "Determines SLA days and priority weight"],
    ["department_id", "INT", "Foreign key, nullable",
     "Populated on assignment"],
    ["assigned_to", "INT", "Foreign key, nullable",
     "The member of staff responsible"],
    ["subject", "VARCHAR(200)", "Not null",
     "Short statement of the problem"],
    ["description", "TEXT", "Not null", "Full detail"],
    ["attachment", "VARCHAR(255)", "Nullable",
     "Randomised filename within the uploads folder"],
    ["is_anonymous", "BOOLEAN", "Default 0",
     "Suppresses the student name in staff views"],
    ["status", "VARCHAR(20)", "Indexed", "Current workflow state"],
    ["priority_score", "INT", "Default 0",
     "Stored score, recomputed on read for ordering"],
    ["reopen_count", "INT", "Default 0",
     "Number of times reopened, contributes to priority"],
    ["created_at", "DATETIME", "Not null", "Submission timestamp"],
    ["updated_at", "DATETIME", "Not null", "Last modification"],
    ["deadline", "DATETIME", "Not null, indexed",
     "Submission timestamp plus the category SLA days"],
    ["resolved_at", "DATETIME", "Nullable",
     "Measurement point for resolution time"],
  ],
  [0.20, 0.16, 0.20, 0.44]));

add(h2("6.3  Indexing strategy"));
add(para(
  "Indexes are placed on the columns that the application actually filters, " +
  "joins or sorts on, rather than on every column."));
add(caption("Table 6.3  Indexes and the operations they support"));
add(table(
  ["Index", "Supports"],
  [
    ["complaints(ticket_code)",
     "Direct lookup from the tracking URL and from the search box"],
    ["complaints(status)", "Status filter and every dashboard count"],
    ["complaints(category_id)", "Category filter and analytics grouping"],
    ["complaints(user_id)", "Student dashboard"],
    ["complaints(assigned_to)", "Staff dashboard and workload counts"],
    ["complaints(department_id)", "Department filter and analytics"],
    ["complaints(deadline)", "SLA breach detection"],
    ["users(email)", "Login and the duplicate registration check"],
    ["complaint_status_history(complaint_id)",
     "Timeline construction on the tracking page"],
    ["comments(complaint_id)", "Comment thread retrieval"],
    ["notifications(user_id, is_read)",
     "A composite index serving the unread count, which is the most " +
     "frequently executed query in the system because every logged in browser " +
     "issues it every fifteen seconds"],
  ],
  [0.35, 0.65]));

add(h2("6.4  Referential integrity"));
add(para(
  "Foreign keys are declared on every relationship. Under MySQL with InnoDB " +
  "these are enforced by default. Under SQLite the connection issues PRAGMA " +
  "foreign_keys equal to ON when it opens, because SQLite does not enforce " +
  "declared foreign keys unless it is explicitly instructed to do so."));

add(h2("6.5  Date storage"));
add(para(
  "All timestamps are stored in the format YYYY-MM-DD HH:MM:SS. MySQL accepts " +
  "this directly as a DATETIME value and SQLite stores it as TEXT. Because " +
  "the format is fixed width and ordered from the most significant unit " +
  "downwards, lexicographic string comparison yields the same ordering as " +
  "chronological comparison. Range filters and ORDER BY therefore behave " +
  "identically on both engines with no conversion."));

// ---- 7. Algorithms ---------------------------------------------------------
add(h1("7.  Core Algorithms"));

add(h2("7.1  Priority score"));
add(para(
  "Ordering a queue by submission date alone allows a genuinely urgent " +
  "complaint to sit behind trivial older ones. Ordering purely by category " +
  "urgency causes the opposite failure, in which low priority complaints are " +
  "never reached. The priority score combines both, together with a penalty " +
  "for complaints that have already failed once."));
add(mono([
  "priority_score = (category.priority_weight  x 10)",
  "               + (days_since_submission     x  2)",
  "               + (reopen_count              x  5)",
]));
add(caption("Table 7.1  Terms of the priority score"));
add(table(
  ["Term", "Weight", "Rationale"],
  [
    ["Category weight", "x 10",
     "The dominant term. A weight of 1 to 5 is assigned per category, so " +
     "examination issues outrank library issues from the moment of submission."],
    ["Age in days", "x 2",
     "Grows without limit. This is the term that guarantees no complaint can " +
     "be starved, because after fifteen days a low weight complaint overtakes " +
     "a freshly submitted high weight one."],
    ["Reopen count", "x 5",
     "A reopened complaint has already consumed the student's patience and " +
     "one failed resolution attempt, so it is escalated."],
  ],
  [0.20, 0.12, 0.68]));

add(h3("Score interpretation"));
add(caption("Table 7.2  Priority bands"));
add(table(
  ["Score range", "Label", "Displayed as"],
  [
    ["60 and above", "Critical", "Red badge"],
    ["40 to 59", "High", "Amber badge"],
    ["25 to 39", "Medium", "Blue badge"],
    ["Below 25", "Low", "Grey badge"],
  ],
  [0.25, 0.20, 0.55]));
add(para(
  "The score is persisted in a column so that it can be indexed, and " +
  "recomputed on read wherever ordering matters. The reason is that the age " +
  "term changes every day while the stored value does not. A derived value " +
  "may be cached, but only if the code is explicit about when the cached " +
  "value is stale. Here the queue always recalculates."));

add(h2("7.2  SLA breach detection"));
add(para(
  "Each category defines sla_days. On submission the deadline is fixed as the " +
  "submission time plus that many days. A complaint is in breach when it " +
  "remains open past its deadline."));
add(mono([
  "if status NOT IN ('Resolved', 'Closed', 'Rejected')",
  "        and now() > deadline:",
  "    breached = True",
]));
add(bullets([
  "Completed complaints are excluded, so a complaint resolved after its " +
  "deadline is not reported as an ongoing breach.",
  "Reopening recalculates the deadline from the reopen moment, which gives " +
  "the department a fresh window rather than an immediate breach.",
  "Breaches surface in three places, namely the administrator dashboard " +
  "panel, the analytics breach table, and a red left border on any affected " +
  "card or row.",
]));

add(h2("7.3  Auto routing classifier"));
add(para("A weighted keyword classifier maps free text onto a department."));
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
add(caption("Table 7.3  Design decisions in the classifier"));
add(table(
  ["Design decision", "Reason"],
  [
    ["Subject weighted three times higher than description",
     "A user states the actual problem in the subject line and supplies " +
     "circumstances in the description, so the subject is the stronger signal."],
    ["Whole word boundary matching",
     "Substring matching yields false positives. The keyword ac, standing for " +
     "air conditioning, would otherwise match inside academics and misroute " +
     "the complaint."],
    ["No suggestion when nothing matches",
     "An arbitrary but confidently presented guess is worse than silence, " +
     "because a busy administrator will accept it without review."],
    ["Suggestion rather than automatic assignment",
     "The classifier advises and the administrator decides, which keeps a " +
     "human accountable for every assignment."],
  ],
  [0.32, 0.68]));
add(para(
  "The keyword vocabularies in helpers.py are the single highest value " +
  "customisation in the codebase. Replacing the generic terms with the " +
  "vocabulary that students at a specific institution actually use, such as " +
  "local block names and colloquial terms for facilities, raises routing " +
  "accuracy immediately with no change to the algorithm."));

// ---- 8. Security -----------------------------------------------------------
add(h1("8.  Security Implementation"));

add(h2("8.1  Measures applied"));
add(caption("Table 8.1  Threats and countermeasures"));
add(table(
  ["Threat", "Countermeasure", "Location"],
  [
    ["SQL injection",
     "Every query is parameterised. No user value is ever formatted into a " +
     "SQL string, including in the dynamic administrator filters, where the " +
     "WHERE clause is assembled from fixed literals and all values travel in " +
     "a separate parameter list.",
     "db.py and _build_where in app.py"],
    ["Password disclosure",
     "Salted PBKDF2 hashing on registration and on reset, with comparison " +
     "performed on hashes only. Seed accounts are inserted by a Python script " +
     "rather than written into the SQL file, so no hash is committed as a " +
     "literal.",
     "app.py and init_db.py"],
    ["Cross site scripting",
     "Jinja2 auto escaping on all server rendered output. Client scripts " +
     "escape text through textContent before insertion. Chart data is " +
     "delivered inside an inert JSON script block that the browser will not " +
     "execute.",
     "Templates, notify.js, analytics template"],
    ["Broken access control",
     "A role decorator on every protected route, together with a record level " +
     "ownership check on every route that addresses a specific complaint.",
     "role_required and can_view in app.py"],
    ["Account enumeration",
     "Login failure and forgot password responses are identical whether or " +
     "not the address is registered.",
     "app.py"],
    ["Malicious file upload",
     "An extension allow list, a 5 MB size cap enforced by the framework, " +
     "filename sanitisation, and a random prefix that prevents overwriting an " +
     "existing file.",
     "helpers.py and config.py"],
    ["Session hijacking",
     "Flask-Login signed session cookies keyed on the application secret.",
     "app.py and config.py"],
    ["Information disclosure through errors",
     "Custom 403, 404, 413 and 500 handlers return a styled page rather than " +
     "a stack trace.",
     "app.py"],
  ],
  [0.18, 0.52, 0.30]));

add(h2("8.2  Parameterisation under dynamic filtering"));
add(para(
  "Dynamic filtering is where injection defects usually appear, because the " +
  "query text varies with user input. The implementation keeps the two " +
  "strictly separate. Clause fragments are appended from fixed string " +
  "literals, while the corresponding values are appended to a parallel " +
  "parameter list. The number of parameters therefore always matches the " +
  "number of placeholders, and no user supplied character ever reaches the " +
  "SQL parser."));
add(mono([
  "if filters['status'] in config.STATUSES:",
  "    clauses.append('c.status = %s')     # fixed literal",
  "    params.append(filters['status'])     # value stays separate",
]));
add(para(
  "The status filter additionally validates the submitted value against the " +
  "known status vocabulary before use, so an unrecognised value is discarded " +
  "rather than passed through as a parameter."));

add(h2("8.3  Deployment hardening required"));
add(para(
  "The delivered configuration is a development configuration. Before any " +
  "deployment outside a laboratory the following measures are mandatory."));
add(bullets([
  "Set debug to False. The Flask debugger exposes an interactive console and " +
  "must never be reachable in a deployed environment.",
  "Replace the application secret with a value drawn from a cryptographically " +
  "secure source, and hold it outside version control.",
  "Serve over HTTPS and set the session cookie to secure and http only.",
  "Run behind a production WSGI server rather than the built in development " +
  "server.",
  "Apply rate limiting to the login and password reset endpoints.",
]));

// ---- 9. Responsive ---------------------------------------------------------
add(h1("9.  Responsive and Mobile First Design"));

add(h2("9.1  Design premise"));
add(para(
  "The user population is assumed to be 98 percent mobile. The interface is " +
  "therefore authored for a 360 pixel screen first, with desktop refinements " +
  "added through minimum width media queries. This is the reverse of the " +
  "common approach of designing for the desktop and reducing afterwards, and " +
  "it yields a different result, in that the phone layout is the designed " +
  "case rather than the degraded one."));

add(h2("9.2  Rules applied"));
add(caption("Table 9.1  Responsive rules and the problems they prevent"));
add(table(
  ["Rule", "Implementation", "Problem prevented"],
  [
    ["Viewport declaration",
     "Present in the base template, inherited by every page",
     "Without it a phone renders the page at desktop width and scales it " +
     "down, which makes all text unreadable"],
    ["Minimum 16 pixel input text",
     "Applied to every input, select and textarea",
     "Safari on iOS zooms the viewport when a field below 16 pixels receives " +
     "focus, so the page jumps on every tap"],
    ["Minimum 44 pixel touch targets",
     "Applied to buttons, navigation links and rating stars",
     "Targets below this size are unreliable with a thumb"],
    ["Tables become cards below 768 pixels",
     "Two renderings of the same data, toggled by a media query",
     "A horizontally scrolling table is technically functional but unusable " +
     "one handed"],
    ["Bottom navigation on phones",
     "A fixed bar with role aware items and reserved body padding",
     "Top navigation is out of thumb reach on a large phone, and without the " +
     "reserved padding the last control is unreachable"],
    ["Filters collapse into an accordion",
     "Collapsed below 768 pixels and forced open above",
     "Seven filter controls would otherwise fill an entire phone screen " +
     "before any result is visible"],
    ["Charts sized by their container",
     "Responsive true, maintainAspectRatio false, fixed height parent",
     "With the aspect ratio disabled and no parent height the canvas " +
     "collapses to zero pixels and the chart silently disappears"],
    ["Horizontal overflow suppressed",
     "Applied at the root, with explicit wrapping on user text",
     "A single long unbroken string would otherwise widen the page and " +
     "introduce sideways scrolling everywhere"],
  ],
  [0.23, 0.35, 0.42]));

add(h2("9.3  Verification"));
add(para(
  "The interface was checked at 320, 360, 768, 1024 and 1440 pixels. At every " +
  "width there is no horizontal page scroll, no truncated text and no " +
  "overlapping element."));

// ---- 10. QA ----------------------------------------------------------------
const QA = [
  ["1", "Landing page loads", "HTTP 200 with hero and statistics", "Pass"],
  ["2", "Login page loads", "HTTP 200 with login form", "Pass"],
  ["3", "Registration page loads", "HTTP 200 with registration form", "Pass"],
  ["4", "Forgot password page loads", "HTTP 200 with mail address form", "Pass"],
  ["5", "Student area protected", "Anonymous request redirected to login", "Pass"],
  ["6", "Staff area protected", "Anonymous request redirected to login", "Pass"],
  ["7", "Administrator area protected", "Anonymous request redirected to login", "Pass"],
  ["8", "Analytics protected", "Anonymous request redirected to login", "Pass"],
  ["9", "Student login and redirect", "Session established, lands on /student", "Pass"],
  ["10", "Student dashboard renders", "Complaint cards and summary tiles", "Pass"],
  ["11", "Administrator login and redirect", "Lands on /admin", "Pass"],
  ["12", "Staff login and redirect", "Lands on /staff", "Pass"],
  ["13", "Student denied administrator area", "Redirected with error message", "Pass"],
  ["14", "Student denied staff area", "Redirected", "Pass"],
  ["15", "Student denied analytics", "Redirected", "Pass"],
  ["16", "Student denied complaint list", "Redirected", "Pass"],
  ["17", "Submission form loads", "HTTP 200 with category dropdown", "Pass"],
  ["18", "Categories populated", "Six categories, each carrying an SLA", "Pass"],
  ["19", "Complaint recorded", "Ticket GRV-2026-0031 issued", "Pass"],
  ["20", "Redirect to tracking page", "Lands on the ticket URL", "Pass"],
  ["21", "First audit row written", "Timeline shows the submission entry", "Pass"],
  ["22", "Status interface responds", "JSON reports the status Pending", "Pass"],
  ["23", "Interface returns deadline", "Formatted deadline present", "Pass"],
  ["24", "Interface audit count", "history_count equals 1 on a new complaint", "Pass"],
  ["25", "Notification interface responds", "Unread count and item list returned", "Pass"],
  ["26", "Priority queue renders", "Ordered by descending priority score", "Pass"],
  ["27", "Breach panel renders", "Overdue complaints listed", "Pass"],
  ["28", "Administrator search", "Query matches the new complaint", "Pass"],
  ["29", "Assignment page loads", "HTTP 200 with staff dropdown", "Pass"],
  ["30", "Auto routing suggestion", "Text containing wifi, printer and lab routed to IT Support", "Pass"],
  ["31", "Workload displayed", "Four staff, each with an open count", "Pass"],
  ["32", "Assignment succeeds", "Redirect with confirmation", "Pass"],
  ["33", "Status becomes Assigned", "Interface confirms Assigned", "Pass"],
  ["34", "Staff dashboard loads", "Shows only assigned complaints", "Pass"],
  ["35", "Assigned ticket visible", "New ticket present in the staff queue", "Pass"],
  ["36", "Status form loads", "HTTP 200 with status dropdown", "Pass"],
  ["37", "Transition to In Progress", "Updated and audited", "Pass"],
  ["38", "Transition to Resolved", "Updated, resolved_at set", "Pass"],
  ["39", "Rating form conditional", "Appears only once resolved", "Pass"],
  ["40", "Rating accepted", "Feedback row written", "Pass"],
  ["41", "Rating closes complaint", "Status becomes Closed", "Pass"],
  ["42", "Reopen succeeds", "Status becomes Reopened", "Pass"],
  ["43", "Reopen resets the SLA", "New deadline, reopen_count incremented", "Pass"],
  ["44", "Comment posted", "Message appears in the thread", "Pass"],
  ["45", "Cross user access denied", "A second student cannot open another student's ticket", "Pass"],
  ["46", "Analytics page loads", "HTTP 200", "Pass"],
  ["47", "Chart data present", "JSON data block rendered", "Pass"],
  ["48", "Average resolution table", "Days and count shown per department", "Pass"],
  ["49", "Top recurring issue", "Largest category identified", "Pass"],
  ["50", "Breach report present", "Overdue complaints tabulated", "Pass"],
  ["51", "Status filter", "Only matching rows returned", "Pass"],
  ["52", "Breached only filter", "Only overdue open rows returned", "Pass"],
  ["53", "Pagination", "Second page returned correctly", "Pass"],
  ["54", "Excel export", "Valid xlsx workbook, verified by file signature", "Pass"],
  ["55", "PDF export view", "Print optimised report renders", "Pass"],
  ["56", "Reset token issued", "Single use link with a one hour expiry", "Pass"],
  ["57", "Password updated", "Hash replaced, token cleared", "Pass"],
  ["58", "Login with new password", "Session established", "Pass"],
  ["59", "Unknown ticket", "Custom 404 page returned", "Pass"],
  ["60", "Input validation", "Short subject and description rejected", "Pass"],
];

add(h1("10.  Quality Assurance and Testing"));

add(h2("10.1  Testing approach"));
add(para(
  "Testing was carried out as automated end to end verification against a " +
  "running instance of the application. A test client issues real HTTP " +
  "requests, maintains real session cookies, submits real form data and " +
  "inspects the responses returned. No function was tested in isolation with " +
  "substituted dependencies."));
add(para(
  "This approach was chosen deliberately. The defects that matter in a system " +
  "of this kind are integration defects, such as a decorator omitted from a " +
  "route, a redirect that loses a session, an ownership check that returns " +
  "the wrong record, or a template variable that is never passed. Unit tests " +
  "with mocked dependencies do not detect any of these. Driving the assembled " +
  "application does."));

add(h2("10.2  Result summary"));
add(caption("Table 10.1  Coverage by functional area"));
add(table(
  ["Area", "Cases", "Passed", "Coverage"],
  [
    ["Public pages", "4", "4", "All unauthenticated routes"],
    ["Access control", "8", "8", "Anonymous redirection and role enforcement"],
    ["Authentication", "4", "4", "Login and role based landing"],
    ["Complaint submission", "5", "5",
     "Validation, ticket assignment, audit initialisation"],
    ["JSON interface", "4", "4", "Status and notification endpoints"],
    ["Assignment and routing", "8", "8",
     "Auto routing suggestion, workload, assignment"],
    ["Staff processing", "5", "5", "Status transitions and auditing"],
    ["Feedback and reopen", "5", "5",
     "Conditional display, rating, SLA reset"],
    ["Comments", "1", "1", "Thread insertion"],
    ["Data isolation", "1", "1", "Cross user record access"],
    ["Analytics and export", "10", "10",
     "All analytics, filters, pagination and both exports"],
    ["Password reset", "3", "3", "Token, update and re-login"],
    ["Error handling", "2", "2", "404 response and input validation"],
    ["Total", "60", "60", "Pass rate 100 percent"],
  ],
  [0.29, 0.11, 0.12, 0.48], ["L", "C", "C", "L"]));

add(h2("10.3  Detailed test cases"));
add(para(
  "The table below lists every executed case with its expected result. The " +
  "actual result matched the expected result in all sixty cases."));
add(caption("Table 10.2  Test case results"));
add(table(
  ["No.", "Test case", "Expected result", "Result"],
  QA,
  [0.07, 0.33, 0.48, 0.12], ["C", "L", "L", "C"]));

add(h2("10.4  Notable verifications"));
add(h3("Data isolation, case 45"));
add(para(
  "A complaint was raised by one student and then requested by a second " +
  "student holding an identical role. Access was refused. This confirms that " +
  "authorisation is enforced per record and not only per role, which is the " +
  "defect class most likely to be missed by role only testing."));
add(h3("Auto routing correctness, case 30"));
add(para(
  "A complaint whose text contained the terms wifi, printer and lab was " +
  "submitted, and the classifier suggested IT Support with no human input. " +
  "This verifies the scoring, the subject weighting and the word boundary " +
  "matching together."));
add(h3("Export integrity, case 54"));
add(para(
  "The spreadsheet export was verified by examining the returned bytes rather " +
  "than the HTTP status code. The response begins with the ZIP container " +
  "signature that identifies a valid Office Open XML workbook and exceeds " +
  "three kilobytes. A test asserting only a 200 response would pass even if " +
  "the endpoint returned an error page."));
add(h3("Lifecycle integrity"));
add(para(
  "Cases 19 to 44 execute the complete lifecycle in sequence against a single " +
  "complaint, covering submission, automatic routing, assignment, two status " +
  "transitions, rating, automatic closure, reopening and commenting. Each " +
  "step reads the state back through the interface rather than assuming that " +
  "the previous step succeeded."));

add(h2("10.5  Manual verification checklist"));
add(para(
  "File handling and visual behaviour cannot be meaningfully asserted over " +
  "HTTP and are verified manually."));
add(caption("Table 10.3  Manual checks"));
add(table(
  ["No.", "Check", "Expected result"],
  [
    ["M1", "Attach a JPG below 5 MB",
     "Stored with a randomised name, link shown on the tracking page"],
    ["M2", "Attach an executable file", "Rejected with a file type message"],
    ["M3", "Attach a file above 5 MB", "Rejected with a size message"],
    ["M4", "Submit anonymously",
     "Staff and administrator views display Anonymous in place of the name"],
    ["M5", "Live status update",
     "Student tracking page updates within five seconds with no reload"],
    ["M6", "Notification bell",
     "Unread badge appears within fifteen seconds of a change"],
    ["M7", "Duplicate mail address on registration",
     "Rejected with a clear message"],
    ["M8", "Mismatched password confirmation", "Rejected before insertion"],
    ["M9", "Interface at 360 pixels",
     "No horizontal scroll, tables render as cards, bottom navigation present"],
    ["M10", "Interface at 1440 pixels",
     "Content column constrained, tables render normally"],
  ],
  [0.08, 0.34, 0.58], ["C", "L", "L"]));

add(h2("10.6  Defects found and resolved"));
add(para(
  "No functional defects remained at the conclusion of testing. Two issues " +
  "were identified and corrected during development."));
add(caption("Table 10.4  Defects and their resolution"));
add(table(
  ["Issue", "Cause", "Resolution"],
  [
    ["Jinja macros rendered without global helper functions",
     "Macros imported into a template do not inherit the template context by " +
     "default, so functions supplied by the context processor were undefined " +
     "inside them.",
     "Every macro import now declares with context."],
    ["Ticket code could not be derived before insertion",
     "The code embeds the row identifier, which is not known until the row " +
     "exists.",
     "Insert with a placeholder code, then immediately update using the " +
     "identifier returned by the insert, which guarantees that the code and " +
     "the row always correspond."],
  ],
  [0.28, 0.40, 0.32]));

// ---- 11. Limitations -------------------------------------------------------
add(h1("11.  Limitations and Future Scope"));

add(h2("11.1  Known limitations"));
add(caption("Table 11.1  Limitations and their reasons"));
add(table(
  ["Limitation", "Current behaviour", "Reason"],
  [
    ["No electronic mail delivery",
     "The password reset link is displayed on screen",
     "No mail server is available in the laboratory. Token issue, expiry and " +
     "single use enforcement are equivalent to a production flow, and only " +
     "the delivery channel differs."],
    ["PDF export uses the browser",
     "A print optimised page is rendered and the browser print dialogue " +
     "writes the file",
     "Avoids a heavyweight rendering dependency that would need installing on " +
     "every machine."],
    ["Polling rather than push",
     "Clients poll at five and fifteen second intervals",
     "Appropriate at institutional scale and traverses restrictive networks " +
     "reliably, although it would not scale to very large user counts."],
    ["Rule based routing",
     "Keyword vocabularies require manual maintenance",
     "Explainable and requires no training data, but does not adapt " +
     "automatically to new terminology."],
    ["Single institution",
     "One department and category set",
     "Multi tenancy was outside the defined scope."],
  ],
  [0.21, 0.32, 0.47]));

add(h2("11.2  Future enhancements"));
add(numbers([
  "Electronic mail and SMS notification on status change, using the existing " +
  "notification records as the delivery queue.",
  "Server sent events or WebSockets in place of polling, which would remove " +
  "periodic requests entirely.",
  "A supervised classifier trained on historical assignments, retaining the " +
  "keyword classifier as an explainable fallback.",
  "Duplicate detection at submission time, identifying complaints about the " +
  "same underlying problem and grouping them.",
  "Escalation rules that reassign or notify a supervisor automatically once a " +
  "complaint passes its deadline.",
  "A staff performance view reporting resolution time and satisfaction rating " +
  "per individual.",
  "A multi language interface, given that grievances are often described most " +
  "precisely in a first language.",
  "A progressive web application manifest enabling installation to the phone " +
  "home screen and offline draft composition.",
]));

// ---- 12. Conclusion --------------------------------------------------------
add(h1("12.  Conclusion"));
add(para(
  "Grievance360 delivers a complete and tested grievance management system. " +
  "Every objective defined in Chapter 2 has been implemented and verified. " +
  "Complaints are submitted from a mobile first interface, issued a unique " +
  "reference, routed automatically, assigned with workload visibility, " +
  "processed through an audited workflow, constrained by a service level " +
  "deadline, ranked by an objective priority score, updated live without a " +
  "page reload, and reported on through analytics with export in two formats."));
add(para(
  "Three design decisions account for most of the durability of the system. " +
  "Isolating database dialect differences at a single boundary allows the " +
  "project to run without a database server while remaining a MySQL " +
  "application, and to switch between the two without editing a query. " +
  "Placing all responsiveness in one inherited base template makes it " +
  "impossible for a new page to be non responsive and allows a layout " +
  "correction to apply everywhere at once. Separating business logic from " +
  "routing keeps each rule in one place where it can be located, explained " +
  "and changed."));
add(para(
  "The audit trail is the feature that addresses the original problem most " +
  "directly. Every status change records what changed, who changed it, when " +
  "and why. That record is what converts a complaint from a request that may " +
  "or may not be acted upon into an accountable commitment with a deadline " +
  "attached."));
add(para(
  "Testing was conducted end to end against the running application and all " +
  "sixty cases pass. The system is complete and functional as delivered."));

// ---- Appendices ------------------------------------------------------------
add(h1("Appendix A  -  Project Structure"));
add(mono([
  "Grievance360/",
  "  app.py                    routes, grouped by role",
  "  config.py                 engine switch, upload rules, statuses",
  "  db.py                     connections, placeholder shim, helpers",
  "  helpers.py                business logic",
  "  init_db.py                schema setup and account seeding",
  "  requirements.txt",
  "  database/",
  "    schema.sql              MySQL schema (canonical)",
  "    schema_sqlite.sql       same tables, SQLite syntax",
  "    sample_data.py          30 demonstration complaints with history",
  "  static/",
  "    css/style.css           all shared layout and responsiveness",
  "    js/track.js             live status polling",
  "    js/notify.js            notification bell polling",
  "    js/charts.js            analytics charts",
  "    uploads/                complaint attachments",
  "  templates/",
  "    base.html               the responsive shell",
  "    partials/_macros.html   reusable components",
  "    student/  staff/  admin/    role specific pages",
]));

add(h2("Appendix B  -  Login Credentials"));
add(caption("Table B.1  Demonstration accounts"));
add(table(
  ["Role", "Mail address", "Password"],
  [
    ["Administrator", "admin@grievance360.edu", "admin123"],
    ["Staff, IT Support", "it.staff@grievance360.edu", "staff123"],
    ["Staff, Maintenance", "maintenance.staff@grievance360.edu", "staff123"],
    ["Staff, Academics", "academics.staff@grievance360.edu", "staff123"],
    ["Staff, Hostel", "hostel.staff@grievance360.edu", "staff123"],
    ["Student", "harsh@student.edu", "student123"],
    ["Student", "priya@student.edu", "student123"],
    ["Student", "arjun@student.edu", "student123"],
  ],
  [0.27, 0.47, 0.26]));
add(para(
  "These accounts exist for demonstration and testing only. They must be " +
  "removed, or have their passwords changed, before any deployment.",
  { size: 11, italics: true }));

add(h2("Appendix C  -  Route Reference"));
add(caption("Table C.1  Application routes"));
add(table(
  ["Route", "Methods", "Access", "Purpose"],
  [
    ["/", "GET", "Public", "Landing page"],
    ["/register", "GET, POST", "Public", "Student registration"],
    ["/login", "GET, POST", "Public", "Authentication"],
    ["/logout", "GET", "Any", "End session"],
    ["/forgot", "GET, POST", "Public", "Issue reset token"],
    ["/reset/token", "GET, POST", "Public", "Set new password"],
    ["/home", "GET", "Any", "Role based redirect"],
    ["/student", "GET", "Student", "Student dashboard"],
    ["/complaint/new", "GET, POST", "Student", "Submit complaint"],
    ["/complaint/code", "GET", "Owner, staff, admin", "Tracking page"],
    ["/complaint/id/comment", "POST", "Owner, staff, admin", "Add comment"],
    ["/complaint/id/feedback", "POST", "Owner", "Submit rating"],
    ["/complaint/id/reopen", "POST", "Owner", "Reopen complaint"],
    ["/staff", "GET", "Staff", "Assigned queue"],
    ["/complaint/id/status", "GET, POST", "Staff, admin", "Update status"],
    ["/admin", "GET", "Administrator", "Dashboard, queue, breaches"],
    ["/admin/complaints", "GET", "Administrator", "Search, filter, paginate"],
    ["/complaint/id/assign", "GET, POST", "Administrator",
     "Auto routing and assignment"],
    ["/admin/analytics", "GET", "Administrator", "Analytics"],
    ["/admin/export/excel", "GET", "Administrator", "Spreadsheet export"],
    ["/admin/export/pdf", "GET", "Administrator", "Printable report"],
    ["/api/complaint/code/status", "GET", "Owner, staff, admin",
     "Live status"],
    ["/api/notifications", "GET", "Any", "Notification list"],
    ["/api/notifications/read", "POST", "Any", "Mark all read"],
  ],
  [0.29, 0.14, 0.22, 0.35]));

// ============================================================== assemble ====
const document = new Document({
  creator: "",
  description: "",
  title: "Grievance360 Project Report",
  // Tells Word to refresh field results when the document opens, so the
  // Contents page fills itself in instead of appearing blank.
  features: { updateFields: true },
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
      {
        reference: "number-list",
        levels: [{
          level: 0,
          format: LevelFormat.DECIMAL,
          text: "%1.",
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
  sections: [
    {
      // Title page: no footer, no page number.
      properties: { page: { margin: MARGIN } },
      children: titlePage(),
    },
    {
      properties: {
        page: { margin: MARGIN, pageNumbers: { start: 1 } },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 120, after: 0 },
            children: [new TextRun({
              children: [PageNumber.CURRENT],
              font: FONT,
              size: half(11),
            })],
          })],
        }),
      },
      children: doc,
    },
  ],
});

const outPath = path.join(__dirname, "Grievance360_Project_Report.docx");
Packer.toBuffer(document).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log("Written: " + outPath);
  console.log("Size:    " + (buf.length / 1024).toFixed(1) + " KB");
});
