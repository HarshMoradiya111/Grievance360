# Grievance360

**A Smart Grievance Redressal & Analytics Portal for Educational Institutions**
MSc-IT Semester 3 project · Python + Flask + SQLite/MySQL + Bootstrap 5.3 + vanilla JS

Students raise grievances from their phones, the system auto-routes them to the
right department, staff work them through a tracked lifecycle, and the admin
sees live analytics, SLA breaches and a priority queue.

---

## Quick start (3 commands)

```bash
python -m pip install -r requirements.txt
```

```bash
python init_db.py
```

```bash
python app.py
```

Then open **http://127.0.0.1:5000**

Optional — load ~30 demo complaints so the dashboard and charts look full:

```bash
python database/sample_data.py
```

---

## Login accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@grievance360.edu` | `admin123` |
| Staff (IT Support) | `it.staff@grievance360.edu` | `staff123` |
| Staff (Maintenance) | `maintenance.staff@grievance360.edu` | `staff123` |
| Staff (Academics) | `academics.staff@grievance360.edu` | `staff123` |
| Staff (Hostel) | `hostel.staff@grievance360.edu` | `staff123` |
| Student | `harsh@student.edu` | `student123` |
| Student | `priya@student.edu` | `student123` |
| Student | `arjun@student.edu` | `student123` |

Students can also register themselves at `/register`. Staff and admin accounts
are created by the administrator (seeded in `init_db.py`).

---

## Switching to MySQL

The project ships on SQLite so it runs with **zero setup**. Every SQL query is
written in MySQL style with `%s` placeholders, so moving to MySQL changes
**one line** and no queries at all.

1. Install MySQL Server 8 and create the schema:
   ```bash
   mysql -u root -p < database/schema.sql
   ```
2. In `config.py` set:
   ```python
   DB_ENGINE = "mysql"
   ```
   and fill in `MYSQL_USER` / `MYSQL_PASSWORD`.
3. Re-seed:
   ```bash
   python init_db.py
   ```

`PyMySQL` (already in `requirements.txt`) is a pure-Python driver, so there is
nothing to compile — unlike `mysqlclient`, which needs Visual Studio build
tools on Windows.

---

## Project structure

```
Grievance360/
├── app.py                  # all routes, grouped by role
├── config.py               # DB engine switch, upload rules, statuses
├── db.py                   # connection + %s/? shim + query helpers
├── helpers.py              # business logic (priority, SLA, auto-routing)
├── init_db.py              # creates tables + seeds accounts
├── requirements.txt
├── database/
│   ├── schema.sql          # MySQL schema (the one for your report)
│   ├── schema_sqlite.sql   # same 8 tables, SQLite syntax
│   ├── sample_data.py      # ~30 demo complaints with full history
│   └── grievance360.db        # created by init_db.py
├── static/
│   ├── css/style.css       # ALL shared layout + responsiveness
│   ├── js/track.js         # live status polling (5s)
│   ├── js/notify.js        # notification bell polling (15s)
│   ├── js/charts.js        # Chart.js analytics
│   └── uploads/            # complaint attachments
└── templates/
    ├── base.html           # the responsive shell every page extends
    ├── partials/_macros.html
    ├── student/  staff/  admin/
```

---

## Database — 8 tables

| Table | Purpose |
|---|---|
| `departments` | Offices that resolve complaints |
| `categories` | Complaint types, each with its own `sla_days` and `priority_weight` |
| `users` | Students, staff and admins in one table, separated by `role` |
| `complaints` | The core record, with ticket code, status, deadline, priority |
| `complaint_status_history` | Audit trail — one row per status change |
| `comments` | Student ↔ staff conversation on a ticket |
| `feedback` | Star rating, one per complaint, only after resolution |
| `notifications` | Feeds the live bell in the navbar |

Indexes on `ticket_code`, `status`, `category_id`, `email`, `deadline`,
`assigned_to`, `department_id`, plus a composite on `(user_id, is_read)` for
the notification bell.

---

## The two key formulas

**Priority score** — `helpers.priority_score()`

```
priority_score = (category.priority_weight × 10)
               + (days_since_created × 2)
               + (reopen_count × 5)
```

Higher = more urgent. The admin priority queue and the staff dashboard both
sort on this, descending. Because the age term keeps growing, an old
low-priority complaint eventually overtakes a fresh high-priority one — nothing
is allowed to sit forgotten.

**SLA breach check** — `helpers.is_breached()`

```
if status NOT IN ('Resolved','Closed','Rejected') AND NOW() > deadline:
    → SLA breached (shown in the red list)
```

`deadline` is set at submission time as `created_at + category.sla_days`.
Reopening a complaint restarts the clock.

---

## Feature map

| Feature | Where |
|---|---|
| Registration + hashed passwords | `app.py` → `register()` |
| Login / logout / sessions | `app.py` → `login()`, flask-login |
| Role-based access control | `app.py` → `role_required()` decorator |
| Forgot / reset password | `app.py` → `forgot_password()`, `reset_password()` |
| Raise complaint + upload + anonymous | `app.py` → `raise_complaint()` |
| Ticket code `GRV-2026-####` | `helpers.make_ticket_code()` |
| SLA deadline on submit | `helpers.add_days()` |
| Student dashboard (cards) | `templates/student/dashboard.html` |
| Track page + timeline | `templates/student/track.html` |
| Auto-routing by keywords | `helpers.suggest_department()` |
| Assign to staff + workload | `app.py` → `assign_complaint()` |
| Staff dashboard + status update | `app.py` → `staff_dashboard()`, `update_status()` |
| Comments | `app.py` → `add_comment()` |
| Feedback + star rating | `app.py` → `submit_feedback()` |
| Reopen | `app.py` → `reopen_complaint()` |
| Priority scoring + queue | `helpers.priority_score()`, admin dashboard |
| JSON status API | `/api/complaint/<code>/status` |
| Live polling (no reload) | `static/js/track.js` |
| Notifications + live bell | `/api/notifications`, `static/js/notify.js` |
| Analytics (GROUP BY) | `app.py` → `admin_analytics()` |
| Avg resolution time per dept | `admin_analytics()`, computed in Python |
| SLA breach report | Admin dashboard + analytics page |
| Top recurring issue | `admin_analytics()` → `top_issue` |
| Charts (pie/bar/line) | `static/js/charts.js` |
| Search, filters, pagination | `app.py` → `_build_where()`, `admin_complaints()` |
| Export Excel | `/admin/export/excel` (openpyxl) |
| Export PDF | `/admin/export/pdf` (print-to-PDF view) |

---

## Mobile-first design

98% of users are students on phones, so the app is built phone-first:

- One `base.html` owns all responsiveness; every page extends it.
- Bottom navigation bar on phones (thumb-reachable), full navbar on desktop.
- Admin tables become **stacked cards** below 768px instead of scrolling sideways.
- All inputs are `16px` — smaller fonts make iOS Safari zoom on focus.
- Every button and link is at least 44×44px.
- Filters collapse into an accordion on phones.
- Charts use `responsive: true` + `maintainAspectRatio: false` inside a
  fixed-height container, one per row on mobile.
- `overflow-x: hidden` on `html, body` — no horizontal page scroll anywhere.

Tested at 320, 360, 768, 1024 and 1440px.

---

## Security

- Passwords hashed with Werkzeug (`generate_password_hash` / `check_password_hash`)
- **Every** SQL query is parameterized — no user input is ever formatted into a
  query string, including the dynamic filters in `_build_where()`
- Role decorators on every protected route
- Ownership checks (`can_view()`) so students only see their own complaints and
  staff only see their department's
- Upload restrictions: extension allow-list + 5 MB cap; stored filenames are
  randomized so uploads cannot overwrite each other
- Login errors are deliberately vague, and the forgot-password page gives the
  same response whether or not the email exists — neither can be used to
  discover which accounts are registered
- Jinja2 auto-escapes all output; the notification JS escapes text before
  inserting it into the DOM

---

## Notes

- Password reset shows the link on screen instead of emailing it, since there
  is no SMTP server in a college lab. The token logic is identical to a real
  email flow — only the delivery differs.
- PDF export opens a print-optimized page; choose "Save as PDF" in the print
  dialog. This keeps the project dependency-free.
- `debug=True` in `app.py` is for development. Turn it off before any real
  deployment, and change `SECRET_KEY` in `config.py`.

See [TEST_CASES.md](TEST_CASES.md) for the test-case table and
[DEMO_SCRIPT.md](DEMO_SCRIPT.md) for the viva click-path.
