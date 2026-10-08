/*
 * Grievance360 - feasibility study and system justification, Word format.
 *
 * Covers: feasibility analysis, why a portal rather than calling, mailing or
 * meeting staff in person, advantages, challenges, issues and their solutions,
 * and the three-person work distribution.
 *
 * Same plain academic formatting as the other documents: Times New Roman,
 * 1.5 line spacing, justified body text, ruled tables, no graphics.
 *
 * Run:
 *     NODE_PATH=/c/Users/harsh/node_modules node docs/build_feasibility_docx.js
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
const BODY_PT = 12;
const TABLE_PT = 10.5;

const MARGIN = { top: 1440, bottom: 1440, left: 1800, right: 1440 };
const CONTENT_W = 11906 - MARGIN.left - MARGIN.right;

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
    pageBreakBefore: true,
    spacing: { before: 0, after: 220, line: 300, lineRule: "auto" },
    children: [new TextRun({ text, font: FONT, size: half(15), bold: true,
                             color: "000000" })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 300, after: 140, line: 300, lineRule: "auto" },
    keepNext: true,
    children: [new TextRun({ text, font: FONT, size: half(13), bold: true,
                             color: "000000" })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 220, after: 110, line: 300, lineRule: "auto" },
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

function table(title, headers, rows, fractions, aligns) {
  tableNo += 1;
  const total = fractions.reduce((a, b) => a + b, 0);
  const widths = fractions.map((f) => Math.round((f / total) * CONTENT_W));
  widths[widths.length - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);

  const alignOf = (i) =>
    aligns && aligns[i] === "C" ? AlignmentType.CENTER : AlignmentType.LEFT;

  return [
    new Paragraph({
      spacing: { before: 160, after: 100 },
      keepNext: true,
      children: [new TextRun({
        text: "Table " + tableNo + "  " + title,
        font: FONT, size: half(11), bold: true,
      })],
    }),
    new Table({
      columnWidths: widths,
      width: { size: CONTENT_W, type: WidthType.DXA },
      rows: [new TableRow({
        tableHeader: true,
        children: headers.map((t, i) =>
          cell(t, widths[i], { head: true, align: alignOf(i) })),
      })].concat(rows.map((r) => new TableRow({
        children: r.map((t, i) => cell(t, widths[i], { align: alignOf(i) })),
      }))),
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
    children: [new TextRun({ text, font: FONT, size: half(size), bold: !!bold })],
  });
}

function titlePage() {
  return [
    titleLine("GRIEVANCE360", 24, true, 160),
    titleLine("A Smart Grievance Redressal and Analytics Portal", 13, false, 40),
    titleLine("for Educational Institutions", 13, false, 760),

    titleLine("FEASIBILITY STUDY", 16, true, 40),
    titleLine("AND SYSTEM JUSTIFICATION", 16, true, 760),

    titleLine("Submitted by", 12, false, 260),
    titleLine("25MSIT077", 13, true, 80),
    titleLine("25MSIT166", 13, true, 80),
    titleLine("25MSIT134", 13, true, 860),

    titleLine("MASTER OF SCIENCE IN INFORMATION TECHNOLOGY", 12, true, 120),
    titleLine("Semester III", 12, false, 60),
    titleLine("August 2026", 12, false, 0),
  ];
}

// ============================================================== content ====
const doc = [];
const add = (x) => { Array.isArray(x) ? doc.push(...x) : doc.push(x); };

// =========================================================================
// 1. FEASIBILITY STUDY
// =========================================================================
add(h1("1.  Feasibility Study"));

add(para(
  "A feasibility study asks whether a proposed system can be built, afforded, " +
  "operated and sustained. The study below examines Grievance360 against five " +
  "standard dimensions and records the conclusion reached in each."));

add(h2("1.1  Technical feasibility"));
add(para(
  "Technical feasibility asks whether the required functionality can be built " +
  "with the skills and equipment available."));
add(table("Technical feasibility assessment",
  ["Requirement", "Available resource", "Assessment"],
  [
    ["Server side programming",
     "Python 3 with the Flask framework, already covered in the syllabus",
     "Feasible"],
    ["Relational storage",
     "MySQL 8, with SQLite for development",
     "Feasible"],
    ["Responsive interface",
     "Bootstrap 5.3 grid and components delivered by CDN",
     "Feasible"],
    ["Live updates without reload",
     "The browser fetch interface polling a JSON endpoint",
     "Feasible. WebSockets would be preferable at large scale but are not " +
     "required at institutional volume"],
    ["Automatic department routing",
     "A weighted keyword classifier written in Python",
     "Feasible. Machine learning was rejected because no labelled training " +
     "data exists and the decisions would not be explainable"],
    ["Charts and analytics",
     "Chart.js with SQL aggregate queries",
     "Feasible"],
    ["Report export",
     "openpyxl for spreadsheets, browser print for PDF",
     "Feasible"],
    ["Development hardware",
     "Standard laboratory desktops and personal laptops",
     "Sufficient. The application has no unusual memory or processing " +
     "requirement"],
  ],
  [0.24, 0.38, 0.38]));
add(para(
  "Conclusion. Every technical requirement is met by tools that are free, " +
  "well documented and already familiar to the team. No component of the " +
  "system depends on technology that the team cannot obtain or learn within " +
  "the project period."));

add(h2("1.2  Economic feasibility"));
add(para(
  "Economic feasibility compares the cost of building and running the system " +
  "against the value it returns."));
add(table("Cost analysis",
  ["Item", "Conventional cost", "Cost to this project"],
  [
    ["Programming language and framework", "Licence fees", "Nil, open source"],
    ["Database engine", "Licence fees", "Nil, open source"],
    ["Front end framework", "Licence or subscription", "Nil, open source"],
    ["Charting library", "Commercial licence", "Nil, open source"],
    ["Spreadsheet export library", "Commercial licence", "Nil, open source"],
    ["PDF rendering engine", "Commercial licence",
     "Nil. The browser print dialogue is used instead"],
    ["Development environment", "Paid IDE licences",
     "Nil. A free code editor is sufficient"],
    ["Hosting during development", "Cloud subscription",
     "Nil. The application runs on a local machine"],
    ["Hosting in production", "Dedicated server",
     "The institution's existing intranet server is adequate. No new hardware " +
     "purchase is required"],
    ["Development effort", "Paid engineering time",
     "Student effort as part of the academic requirement"],
  ],
  [0.32, 0.30, 0.38]));
add(para(
  "The direct monetary cost of the software stack is nil. The costs that " +
  "remain are staff time for handling complaints, which the institution " +
  "already incurs today through telephone calls and office visits, and a " +
  "small amount of administrator time for account setup."));
add(para(
  "Against this, the system returns time saved. A grievance raised today is " +
  "typically repeated several times through different channels before it " +
  "reaches the right person, and each repetition consumes staff attention. A " +
  "single routed ticket replaces those repetitions. The system also prevents " +
  "duplicated effort by making it visible when several students report the " +
  "same underlying problem."));
add(para(
  "Conclusion. The system is economically feasible. It requires no purchase, " +
  "no licence and no new hardware."));

add(h2("1.3  Operational feasibility"));
add(para(
  "Operational feasibility asks whether the intended users will actually use " +
  "the system, and whether the institution can sustain it."));
add(table("Operational feasibility by user group",
  ["User group", "Concern", "How the design addresses it"],
  [
    ["Students",
     "Will they submit a complaint online rather than complaining verbally?",
     "The interface is mobile first and a complaint takes under a minute to " +
     "submit. Students already carry the device required. Anonymity is " +
     "offered for complaints they would not raise face to face."],
    ["Staff",
     "Will they treat a queue of tickets as real work?",
     "Each ticket carries a deadline and appears in a single ordered list " +
     "rather than arriving through several channels. A remark is mandatory on " +
     "every change, so the work performed is recorded rather than forgotten."],
    ["Administration",
     "Will assigning complaints add to an already heavy workload?",
     "Auto routing proposes the department, and the staff dropdown shows " +
     "current workload, so assignment is a confirmation rather than an " +
     "investigation."],
    ["Institution",
     "Can the system be maintained after the project ends?",
     "The codebase is small, conventional and documented. Category, department " +
     "and keyword configuration is data rather than code, so ordinary changes " +
     "need no programming."],
  ],
  [0.16, 0.31, 0.53]));
add(para(
  "Conclusion. The system is operationally feasible, subject to the adoption " +
  "measures set out in Chapter 4."));

add(h2("1.4  Schedule feasibility"));
add(para(
  "Schedule feasibility asks whether the system can be delivered within the " +
  "academic period available."));
add(table("Schedule against the academic period",
  ["Phase", "Duration", "Deliverable"],
  [
    ["Requirement study and design", "Week 1",
     "Objectives, module split, database schema"],
    ["Database and base interface", "Week 1 to 2",
     "Eight tables with indexes, the shared responsive layout"],
    ["Authentication and roles", "Week 2",
     "Registration, login, role control, password reset"],
    ["Complaint lifecycle", "Week 3 to 4",
     "Submission, tracking, assignment, processing, feedback"],
    ["Live updates and notifications", "Week 5",
     "JSON endpoints, polling clients, notification records"],
    ["Analytics and reporting", "Week 5 to 6",
     "Aggregate queries, charts, filters, exports"],
    ["Testing and hardening", "Week 6 to 7",
     "Sixty test cases, validation, security review"],
    ["Documentation", "Week 7 to 8",
     "Report, test records, demonstration script"],
  ],
  [0.28, 0.16, 0.56]));
add(para(
  "Conclusion. The schedule is feasible within eight weeks for a team of " +
  "three working in parallel on separate modules, with weekly integration."));

add(h2("1.5  Legal and ethical feasibility"));
add(para(
  "The system stores personal data, namely name, mail address, enrolment " +
  "number, telephone number and the content of grievances. Some of that " +
  "content is sensitive by nature. The following measures address the " +
  "resulting obligations."));
add(bullets([
  "Passwords are stored only as salted hashes and are never recoverable in " +
  "readable form.",
  "Access is restricted by role and additionally by record ownership, so a " +
  "grievance is visible only to the person who raised it, the assigned member " +
  "of staff and the administrator.",
  "Anonymous submission is supported for grievances a student would not raise " +
  "under their own name.",
  "Uploaded files are restricted by type and size, and stored under " +
  "randomised names so that one upload cannot overwrite another.",
  "The audit trail is append only in practice, so the record of who did what " +
  "cannot be quietly revised.",
]));
add(para(
  "Accreditation and regulatory frameworks for higher education commonly " +
  "require an institution to operate a documented grievance redressal " +
  "mechanism and to be able to demonstrate that grievances are acted upon. A " +
  "system that records every submission, every status change and the time " +
  "taken to resolve satisfies that requirement in a way that an informal " +
  "verbal process cannot."));
add(para(
  "Conclusion. The system is legally and ethically feasible provided the " +
  "hardening measures listed in the main report are applied before deployment."));

add(h2("1.6  Feasibility summary"));
add(table("Summary of the feasibility study",
  ["Dimension", "Verdict", "Principal reason"],
  [
    ["Technical", "Feasible",
     "All components are open source and within the team's competence"],
    ["Economic", "Feasible", "Nil licensing cost and no new hardware"],
    ["Operational", "Feasible",
     "Mobile first submission, automatic routing, and configuration held as " +
     "data rather than code"],
    ["Schedule", "Feasible",
     "Eight weeks for three members working on separate modules"],
    ["Legal and ethical", "Feasible",
     "Hashing, role and ownership control, anonymity, and an audit trail"],
  ],
  [0.20, 0.14, 0.66]));

// =========================================================================
// 2. WHY A PORTAL
// =========================================================================
add(h1("2.  Why a Portal Rather Than Existing Channels"));

add(para(
  "The most reasonable objection to this project is that students can already " +
  "telephone a member of staff, send an electronic mail, or walk to an office " +
  "and explain the problem in person. Those channels exist, cost nothing and " +
  "require no software. This chapter examines why they are nevertheless " +
  "inadequate, and what the portal provides that none of them can."));

add(h2("2.1  How a grievance is handled today"));
add(para(
  "A student notices a problem, for example a ceiling fan that has stopped " +
  "working. The student does not know which office is responsible, so they " +
  "mention it to whichever member of staff they next encounter. That person " +
  "may pass it on, may intend to pass it on, or may reasonably assume someone " +
  "else has already reported it. If nothing changes, the student has no way " +
  "to check what happened, and no evidence that the problem was ever " +
  "reported. After a second or third attempt most students stop reporting."));
add(para(
  "The failure here is not indifference on anyone's part. It is that the " +
  "process has no memory. Nothing in it records that a request was made, who " +
  "accepted it, or when it was due."));

add(h2("2.2  Limitations of the telephone call"));
add(bullets([
  "No record. When the call ends nothing remains. If the problem is not " +
  "fixed, the student cannot demonstrate that it was ever reported, and the " +
  "member of staff cannot demonstrate that it was passed on.",
  "No deadline. A conversation cannot carry a service level. Nothing marks " +
  "the request as overdue, because nothing recorded when it began.",
  "Availability mismatch. Staff are teaching or in meetings during precisely " +
  "the hours when students are free to call, and the reverse. A portal accepts " +
  "a submission at any hour and does not require both parties to be free at " +
  "the same moment.",
  "The student must know whom to call. The most common reason a grievance is " +
  "delayed is that it reached the wrong office first. The student is being " +
  "asked to solve a routing problem that the institution is better placed to " +
  "solve.",
  "No aggregation. If forty students telephone about the same failed network " +
  "switch, the institution receives forty interruptions and no signal that " +
  "these are one problem.",
  "Repetition falls on the student. Following up means calling again, which " +
  "is socially uncomfortable when the other party is a member of teaching " +
  "staff who assesses them.",
]));

add(h2("2.3  Limitations of electronic mail"));
add(para(
  "Mail is better than a telephone call because it leaves a written record. " +
  "It nevertheless falls short in ways that matter."));
add(bullets([
  "A mail message has no state. There is no Pending, no In Progress and no " +
  "Resolved. The only way to learn the position is to send another message " +
  "asking.",
  "A mailbox cannot be queried. Nobody can ask how many grievances about the " +
  "hostel are currently open, or how long the maintenance office takes on " +
  "average, because the information is scattered across individual mailboxes.",
  "There is no deadline and no escalation. A message that is not answered " +
  "simply moves down the inbox.",
  "Routing is still the student's problem. A message sent to the wrong " +
  "address is forwarded, or is not.",
  "Unstructured content. A free text message may omit the room number, the " +
  "block or the date, so the first reply is usually a request for the " +
  "information that a structured form would have required at submission.",
  "Anonymity is impossible. The address identifies the sender, so a grievance " +
  "that a student is unwilling to attach their name to will not be sent at all.",
  "No institutional memory. When a member of staff leaves, the mailbox and " +
  "everything in it leaves with them.",
]));

add(h2("2.4  Limitations of meeting in person"));
add(bullets([
  "It is the most expensive channel for both parties. The student leaves a " +
  "class or waits outside an office; the member of staff is interrupted.",
  "It shares every weakness of the telephone call, since the outcome is again " +
  "an unrecorded conversation.",
  "It advantages the confident. Students who are articulate, senior or " +
  "personally known to staff are served sooner than students who are none of " +
  "those things. The same grievance receives different treatment depending on " +
  "who carries it.",
  "It is impossible for an entire class of grievance. A student cannot " +
  "reasonably raise a complaint about harassment, about ragging, or about a " +
  "specific member of staff by walking into that person's office.",
]));

add(h2("2.5  Comparison of channels"));
add(table("Existing channels compared with the portal",
  ["Criterion", "Telephone call", "Electronic mail", "In person", "Portal"],
  [
    ["Permanent record of the request", "No", "Partial", "No", "Yes"],
    ["Reference number the student can quote", "No", "No", "No", "Yes"],
    ["Defined resolution deadline", "No", "No", "No", "Yes"],
    ["Overdue requests reported automatically", "No", "No", "No", "Yes"],
    ["Status visible without asking again", "No", "No", "No", "Yes"],
    ["Automatic routing to the right office", "No", "No", "No", "Yes"],
    ["Works when the other party is unavailable", "No", "Yes", "No", "Yes"],
    ["Anonymous submission possible", "No", "No", "No", "Yes"],
    ["Structured information captured at source", "No", "No", "No", "Yes"],
    ["Photographic evidence attached", "No", "Yes", "No", "Yes"],
    ["Repeated reports identified as one problem", "No", "No", "No", "Yes"],
    ["Workload visible before assignment", "No", "No", "No", "Yes"],
    ["Average resolution time measurable", "No", "No", "No", "Yes"],
    ["Survives staff turnover", "No", "No", "No", "Yes"],
    ["Outcome rated by the student", "No", "No", "No", "Yes"],
    ["Reopening tracked as a separate event", "No", "No", "No", "Yes"],
  ],
  [0.34, 0.16, 0.17, 0.14, 0.13],
  ["L", "C", "C", "C", "C"]));

add(h2("2.6  What the portal provides that no direct channel can"));
add(numbers([
  "A reference number. The ticket code converts a request into an object that " +
  "both parties can refer to. This single change is what makes every " +
  "subsequent guarantee possible.",

  "A deadline attached to the request itself. Each category carries its own " +
  "service level, so a failed network connection is due in two days while a " +
  "library request is due in ten. No conversation can carry that.",

  "Escalation that does not depend on the student. The priority score rises " +
  "every day a complaint remains open, so an ignored grievance moves up the " +
  "queue automatically. In every direct channel, escalation means the student " +
  "must ask again, which is exactly what a student is least willing to do.",

  "Routing performed by the system. The student describes the problem in " +
  "ordinary language and the system proposes the responsible department. The " +
  "student is no longer required to know the institution's internal structure " +
  "before they can report a broken fan.",

  "Anonymity where it is needed. A grievance concerning harassment, ragging, " +
  "or the conduct of a member of staff cannot be raised through a channel " +
  "that identifies the sender to the person complained about. The portal " +
  "accepts it, tracks it and still allows the student to follow progress.",

  "Aggregation. Forty reports of the same failure appear as one category with " +
  "forty entries, and the analytics identify it as the largest recurring " +
  "issue. No volume of telephone calls produces that insight.",

  "Fairness. Complaints are ordered by an objective score rather than by who " +
  "is most persistent or best connected.",

  "Measurement. The institution can state how many grievances were received, " +
  "how many were resolved within the service level, and how long each " +
  "department took. A process that is not recorded cannot be improved, and " +
  "cannot be shown to an accrediting body.",

  "Institutional memory. The record belongs to the institution rather than to " +
  "an individual mailbox, so it survives a change of staff.",
]));

add(h2("2.7  The portal does not replace the conversation"));
add(para(
  "It is worth stating plainly what the system does not claim. It does not " +
  "argue that speaking to a member of staff is undesirable, and it does not " +
  "attempt to remove human contact from the process. A member of staff will " +
  "still inspect the fan, and will still speak to the student where that is " +
  "the quickest route to a solution."));
add(para(
  "What the portal changes is that the conversation now takes place against a " +
  "record. The comment thread on each ticket carries the same discussion that " +
  "would have happened by telephone, but attached to a request that has a " +
  "reference number, a deadline and an owner. The human element is retained; " +
  "what is added is memory and accountability."));
add(para(
  "Stated in one sentence: the alternatives can solve a problem, but only a " +
  "recorded system can prove that the problem was raised, show who accepted " +
  "it, enforce when it was due, and reveal that it has been raised forty " +
  "times before."));

// =========================================================================
// 3. ADVANTAGES
// =========================================================================
add(h1("3.  Advantages"));

add(h2("3.1  Advantages to students"));
add(bullets([
  "A grievance can be submitted in under a minute from a mobile telephone, at " +
  "any hour, without locating the responsible office first.",
  "A ticket code provides proof that the grievance was raised.",
  "The status timeline shows exactly what has happened and who did it, " +
  "without the student having to ask.",
  "The page updates itself, so progress can be seen without a reload.",
  "Anonymous submission allows grievances that would otherwise never be " +
  "raised at all.",
  "A photograph can be attached, which frequently removes an entire round of " +
  "clarification.",
  "The rating and reopen controls give the student a say in whether the " +
  "matter is genuinely closed, rather than allowing it to be closed over them.",
]));

add(h2("3.2  Advantages to staff"));
add(bullets([
  "One ordered queue replaces requests arriving by telephone, in corridors " +
  "and by mail.",
  "The queue is sorted by priority score, so the question of what to work on " +
  "next is already answered.",
  "Each complaint arrives with a category, a description, a location and " +
  "often a photograph, so less time is spent establishing the basic facts.",
  "Recorded remarks demonstrate the work performed, which protects staff as " +
  "much as it informs students.",
  "Workload is visible at the point of assignment, so complaints are " +
  "distributed rather than concentrated on whoever is most responsive.",
]));

add(h2("3.3  Advantages to the administration"));
add(bullets([
  "A single view of every grievance in the institution, filterable by status, " +
  "category, department and date.",
  "Automatic identification of complaints that have passed their deadline.",
  "Average resolution time per department, which converts an impression about " +
  "performance into a measurement.",
  "Identification of the largest recurring issue, which directs effort at " +
  "root causes rather than at individual symptoms.",
  "Exportable reports for review meetings and accreditation records.",
  "Evidence that a documented grievance mechanism exists and is used.",
]));

add(h2("3.4  Advantages to the institution"));
add(bullets([
  "Grievances that were previously abandoned after one unsuccessful attempt " +
  "now enter a record, so the true volume becomes visible.",
  "Accountability is distributed to a named owner with a deadline rather than " +
  "resting on whoever was told first.",
  "Repeated problems are addressed at the source, which reduces the total " +
  "number of grievances over time.",
  "Student confidence improves when a request visibly receives a reference " +
  "number and a deadline.",
  "The record survives staff turnover.",
]));

// =========================================================================
// 4. CHALLENGES
// =========================================================================
add(h1("4.  Challenges"));

add(para(
  "The challenges below are stated as they were encountered or anticipated, " +
  "together with the position taken on each. A challenge that has been " +
  "resolved is marked as such; one that remains open is stated honestly as " +
  "open."));

add(h2("4.1  Technical challenges"));
add(table("Technical challenges",
  ["Challenge", "Position taken"],
  [
    ["Supporting MySQL for assessment while running without a database server " +
     "in the laboratory",
     "Resolved. Every query is written in MySQL style and a four line shim " +
     "translates placeholders for SQLite. Switching engines changes one line " +
     "of configuration and no queries."],
    ["Delivering live updates without a persistent connection",
     "Resolved by polling at a five second interval. WebSockets would be " +
     "preferable at large scale but add a dependency and are blocked by some " +
     "institutional networks."],
    ["Presenting wide administrative tables on a 360 pixel screen",
     "Resolved. Below 768 pixels the same data renders as stacked cards " +
     "rather than a table that scrolls sideways."],
    ["Keeping a derived priority score correct as complaints age",
     "Resolved. The score is stored so it can be indexed, and recomputed on " +
     "read wherever ordering matters, because the age term changes daily."],
    ["Preventing complaint text from executing as markup in the interface",
     "Resolved. Server output is auto escaped, client scripts escape through " +
     "textContent, and chart data is delivered in an inert JSON block."],
    ["Two users uploading files of the same name",
     "Resolved. Stored filenames carry a random prefix."],
  ],
  [0.36, 0.64]));

add(h2("4.2  Adoption and organisational challenges"));
add(table("Adoption challenges",
  ["Challenge", "Position taken"],
  [
    ["Students may continue to complain verbally out of habit",
     "Open. Mitigated by making submission faster than finding the right " +
     "office, and by publicising the ticket code as proof. Requires " +
     "institutional endorsement to succeed fully."],
    ["Staff may regard the queue as additional work rather than the same work " +
     "recorded",
     "Open. Mitigated by the fact that the queue replaces rather than adds to " +
     "existing channels, and by mandatory remarks that evidence work done."],
    ["Complaints may be closed without genuinely being resolved",
     "Partly addressed. The student rates the outcome and may reopen, which " +
     "increments a visible counter and restarts the deadline."],
    ["The system may be used for frivolous or repeated submissions",
     "Open. No automatic filtering is applied, on the view that suppressing " +
     "submissions is worse than receiving some that are unfounded. The " +
     "Rejected status with a mandatory remark handles these transparently."],
    ["Keyword vocabularies drift as institutional language changes",
     "Open by design. The vocabularies are held as ordinary data so that a " +
     "non programmer can update them."],
  ],
  [0.36, 0.64]));

add(h2("4.3  Data and privacy challenges"));
add(table("Data and privacy challenges",
  ["Challenge", "Position taken"],
  [
    ["Grievances may contain sensitive personal information",
     "Addressed by role based access combined with record level ownership " +
     "checks, so a grievance is visible only to the student, the assigned " +
     "member of staff and the administrator."],
    ["Anonymous complaints must remain anonymous to staff while still being " +
     "trackable by the student",
     "Addressed. The identifier is retained for notification and tracking but " +
     "suppressed in every staff and administrator view."],
    ["An administrator can see all grievances, including sensitive ones",
     "Open. This is inherent in having an administrator role. Mitigated by " +
     "the audit trail, which records every action taken."],
    ["Development credentials are present in the delivered configuration",
     "Documented. The hardening list requires their removal before deployment."],
  ],
  [0.36, 0.64]));

// =========================================================================
// 5. ISSUES AND SOLUTIONS
// =========================================================================
add(h1("5.  Issues Encountered and Solutions Applied"));

add(para(
  "The issues below arose during development and testing. Each is recorded " +
  "with the symptom observed, the underlying cause and the correction applied."));

add(table("Issues encountered during development",
  ["No.", "Issue", "Cause", "Solution applied"],
  [
    ["1", "Helper functions were undefined inside reusable interface " +
     "components",
     "Jinja macros imported into a template do not inherit the template " +
     "context by default, so functions supplied by the context processor were " +
     "not visible inside them.",
     "Every macro import now declares with context."],

    ["2", "The ticket code could not be derived before the row was inserted",
     "The code embeds the row identifier, which the database does not assign " +
     "until insertion completes.",
     "Insert with a placeholder code, then update immediately using the " +
     "identifier returned, which guarantees the code and the row always " +
     "correspond."],

    ["3", "Date functions differed between the two database engines",
     "MySQL provides NOW, DATE_ADD and TIMESTAMPDIFF while SQLite provides " +
     "julianday and strftime. Using either would have required two versions " +
     "of several queries.",
     "All date arithmetic moved into Python and passed as parameters, leaving " +
     "one set of queries that runs on both engines."],

    ["4", "Foreign keys were not being enforced during development",
     "SQLite ignores declared foreign keys unless explicitly instructed to " +
     "enforce them.",
     "The connection issues the enforcement pragma when it opens."],

    ["5", "Charts vanished on the analytics page",
     "With the aspect ratio disabled and no height on the parent element, the " +
     "canvas collapses to zero pixels and renders nothing, without raising an " +
     "error.",
     "Each chart is placed inside a container with an explicit height."],

    ["6", "The page jumped whenever a form field was tapped on a telephone",
     "Safari on iOS zooms the viewport when a field with text below 16 pixels " +
     "receives focus.",
     "A minimum of 16 pixels applied to every input, select and textarea."],

    ["7", "Administrative tables were unusable on a telephone",
     "A table of nine columns cannot fit a 360 pixel screen and forces " +
     "sideways scrolling.",
     "Below 768 pixels the same rows render as stacked cards."],

    ["8", "The final control on a page could not be tapped",
     "The fixed bottom navigation bar covered the last portion of the page.",
     "Body padding equal to the height of the bar is reserved on small screens."],

    ["9", "Old low priority complaints were never reached",
     "Ordering by category weight alone allowed them to remain permanently " +
     "below newer high priority complaints.",
     "An age term was added to the priority score, so a complaint rises " +
     "steadily and eventually overtakes newer ones."],

    ["10", "A complaint resolved after its deadline continued to be reported " +
     "as a breach",
     "The breach test considered only the deadline.",
     "The test now excludes complaints in Resolved, Closed or Rejected states."],

    ["11", "A reopened complaint was immediately in breach",
     "The original deadline had already passed when the complaint was " +
     "reopened.",
     "Reopening recalculates the deadline from the reopen moment and " +
     "increments a counter that raises the priority score."],

    ["12", "The keyword ac, for air conditioning, routed academic complaints " +
     "to maintenance",
     "Substring matching found the sequence inside the word academics.",
     "Matching now requires whole word boundaries."],

    ["13", "The classifier produced a confident suggestion for text " +
     "containing no relevant keywords",
     "The highest scoring department was proposed even when every score was " +
     "zero.",
     "No suggestion is offered when nothing matches, and the administrator is " +
     "asked to choose."],

    ["14", "Two students uploading a file of the same name overwrote one " +
     "another",
     "The original filename was used as the stored filename.",
     "A random prefix is added to every stored filename."],

    ["15", "A student holding the correct role could open another student's " +
     "grievance",
     "Authorisation was enforced by role alone, which is satisfied by any " +
     "student.",
     "A record level ownership check was added to every route that addresses " +
     "a specific complaint, and is verified by a dedicated test case."],
  ],
  [0.05, 0.26, 0.32, 0.37],
  ["C", "L", "L", "L"]));

// =========================================================================
// 6. WORK DISTRIBUTION
// =========================================================================
add(h1("6.  Work Distribution Across Three Members"));

add(para(
  "The system was divided into three areas of ownership so that the three " +
  "members could work in parallel without editing the same files. The " +
  "division follows the natural seams in the architecture rather than " +
  "splitting work arbitrarily by file count."));

add(table("Ownership by member",
  ["Member", "Area of ownership", "Modules"],
  [
    ["Member A", "Authentication and the student experience",
     "M1 Authentication and Access Control, M2 Complaint Submission, " +
     "M3 Complaint Tracking and Interaction"],
    ["Member B", "Administrative and staff workflow",
     "M4 Assignment and Auto Routing, M5 Complaint Processing"],
    ["Member C", "Live updates, analytics and reporting",
     "M6 Notification and Live Update, M7 Analytics and Reporting"],
  ],
  [0.14, 0.32, 0.54]));

add(h2("6.1  Member A - authentication and student experience"));
add(bullets([
  "Registration with full field validation and duplicate address rejection.",
  "Login, session management and logout using Flask-Login.",
  "The role decorator that protects every non public route, and the record " +
  "level ownership check.",
  "Password reset using a single use token with a one hour expiry.",
  "The complaint submission form, including file upload validation, filename " +
  "randomisation and the anonymous option.",
  "Ticket code assignment and the service level deadline calculation.",
  "The student dashboard rendered as responsive cards.",
  "The tracking page, including the vertical status timeline built from the " +
  "audit table.",
  "The comment thread, the rating form and the reopen path.",
]));

add(h2("6.2  Member B - administrative and staff workflow"));
add(bullets([
  "The administrative dashboard with summary counts, the priority queue and " +
  "the breach panel.",
  "The complaint listing with search across four fields, filtering by status, " +
  "category, department and date range, and pagination.",
  "The weighted keyword classifier for automatic department routing, " +
  "including whole word matching and the decision to withhold a suggestion " +
  "when nothing matches.",
  "The assignment screen, including the workload count shown against each " +
  "member of staff and the department filter.",
  "The staff dashboard sorted by live priority score.",
  "The status update workflow with mandatory remarks.",
  "The audit trail, written on every status change.",
  "The priority score algorithm and the service level breach test.",
]));

add(h2("6.3  Member C - live updates, analytics and reporting"));
add(bullets([
  "The JSON status endpoint and the notification endpoints.",
  "The tracking client that polls at five second intervals and updates the " +
  "interface in place.",
  "The notification bell client, its unread counter and the escaping applied " +
  "before insertion into the document.",
  "The notification records written on assignment, status change, comment and " +
  "reopen.",
  "The aggregate queries for distribution by status, category and department.",
  "Average resolution time per department, computed for engine independence.",
  "The service level breach report and the top recurring issue analytic.",
  "Four charts rendered responsively.",
  "Spreadsheet export with styled headers, and the print optimised report view.",
]));

add(h2("6.4  Shared work"));
add(bullets([
  "The database schema of eight tables with foreign keys and eleven indexes, " +
  "designed jointly before any feature work began.",
  "The shared responsive base template that every page extends.",
  "The stylesheet that owns all shared layout.",
  "Weekly integration, with the full lifecycle exercised end to end.",
  "The sixty test cases and the documentation set.",
]));

add(h2("6.5  Quantitative summary"));
add(table("Scale of the delivered system",
  ["Measure", "Count"],
  [
    ["Functional modules", "7"],
    ["Database tables", "8"],
    ["Indexes", "11"],
    ["Application routes", "24"],
    ["JSON endpoints", "3"],
    ["Interface templates", "16"],
    ["Client script files", "3"],
    ["Complaint statuses in the workflow", "7"],
    ["Documented algorithms", "3"],
    ["Automated test cases", "60"],
    ["Manual verification checks", "10"],
  ],
  [0.62, 0.38], ["L", "C"]));

add(para(
  "The division gives each member a complete vertical slice, that is, database " +
  "queries, business logic, routes and interface for their own area, rather " +
  "than one member writing all the queries and another all the templates. " +
  "Each member is therefore able to explain their portion end to end."));

// =========================================================================
// 7. CONCLUSION
// =========================================================================
add(h1("7.  Conclusion"));

add(para(
  "The feasibility study finds the system feasible on all five dimensions " +
  "examined. It requires no purchase, no licence and no new hardware, it uses " +
  "technology within the team's competence, and it can be delivered within " +
  "the academic period by three members working on separate modules."));

add(para(
  "The case for a portal rather than a telephone call, a mail message or an " +
  "office visit does not rest on those channels being difficult. It rests on " +
  "the fact that none of them produces a record. Without a record there is no " +
  "reference number, no deadline, no automatic escalation, no measurement of " +
  "how long a department takes, no way to see that forty students have " +
  "reported the same failure, and no possibility of raising a grievance " +
  "anonymously. The portal does not replace the conversation with a member of " +
  "staff. It gives that conversation a reference number, an owner and a date " +
  "by which it is due."));

add(para(
  "The advantages are distributed across all four groups affected. Students " +
  "gain proof and visibility, staff gain a single ordered queue and evidence " +
  "of work performed, the administration gains measurement, and the " +
  "institution gains a documented mechanism that survives staff turnover."));

add(para(
  "The challenges are recorded honestly. The technical challenges were " +
  "resolved during development. The adoption challenges remain genuinely " +
  "open, because they depend on institutional endorsement rather than on " +
  "software, and no amount of engineering can fully substitute for that."));

// ============================================================== assemble ====
const document = new Document({
  creator: "",
  description: "",
  title: "Grievance360 Feasibility Study and System Justification",
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

const outPath = path.join(__dirname,
  "Grievance360_Feasibility_And_Justification.docx");
Packer.toBuffer(document).then((buf) => {
  fs.writeFileSync(outPath, buf);
  console.log("Written: " + outPath);
  console.log("Size:    " + (buf.length / 1024).toFixed(1) + " KB");
  console.log("Tables:  " + tableNo);
});
