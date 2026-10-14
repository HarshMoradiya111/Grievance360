# Grievance360

**A Smart Grievance Redressal, Intelligent Automation & Analytics Portal for Educational Institutions**  
*Python 3.14 · Flask 3.1 · MongoDB Atlas (PyMongo) · Bootstrap 5.3 · Chart.js · Vanilla JS*

---

## Overview

**Grievance360** is a modern, full-featured grievance redressal and workflow automation portal designed specifically for colleges and universities. It replaces traditional paper registers and unmonitored email inboxes with a transparent, statutorily compliant (UGC/AICTE) digital grievance lifecycle.

Students file grievances across categories with optional anonymous reporting and file attachments. Behind the scenes, an **Intelligent Automation Engine** handles zero-touch staff assignment, fast-tracks emergencies, detects duplicates, monitors SLA deadlines via background daemons, fires pre-breach early warnings, and auto-closes resolved complaints.

---

## Key Modules & Autonomous Systems

### 1. Student Portal & Grievance Intake
- **Category-Based Filing:** Pre-configured SLA turnaround windows (e.g., 2 days for IT, 5 days for Academics).
- **Anonymous Whistleblower Protection:** Masks student identity on all faculty screens while preserving secure notifications.
- **Secure Evidence Uploads:** File validation for PNG, JPG, PDF, and DOCX with randomized 12-hex UUID filenames.
- **Live Ticket Tracking (`GRV-YYYY-NNNN`):** Interactive status timeline, two-way dialogue comments, and 1-click CSAT star ratings.

### 2. Intelligent Automation Engine (`automation.py`)
- **Zero-Touch Staff Auto-Assignment:** Evaluates active staff ticket counts and instantly dispatches cases to the least-burdened officer.
- **NLP Emergency & Anti-Ragging Fast-Track:** Automatically detects safety keywords (*ragging, harassment, assault, medical, fire*); sets priority to **100 (Critical)**, cuts SLA to **24 hours**, and triggers urgent alerts to Security and the Principal.
- **Jaccard Duplicate Detection & Supporter Linkage:** Identifies similar active complaints ($J \ge 0.50$); auto-tags duplicates and links submitters as supporters ("Me Too" backers).
- **Autonomous SLA Escalation Daemon:** Background sweep thread (`scheduler.py`) evaluates elapsed SLA ratios and elevates overdue tickets across Level 1 (Staff), Level 2 (HOD), and Level 3 (Dean).
- **Predictive SLA Pre-Breach Early Warnings:** Proactive alerts dispatched to staff when a ticket hits 75% elapsed SLA without resolution.
- **Stalled Ticket Nudge Engine:** Sends automated reminders when an assigned grievance sits for $\ge 48$ hours with zero staff activity.
- **5-Day Grace Period Auto-Closure:** Automatically closes resolved tickets after 5 days if uncontested by the student.
- **Post-Resolution CSAT Feedback Trigger:** Dispatches an automated 1-to-5 star feedback survey the instant a case is marked resolved.
- **Multi-Reopen Escalation to Dean:** Re-routing grievances reopened $\ge 2$ times directly to the Dean / Institutional Ombudsperson.
- **Campus Outage & Spike Anomaly Detector:** Flags sudden grievance bursts ($\ge 4$ complaints in 2 hours under the same category) and drafts public campus advisories.
- **Executive Analytics Digest:** Compiles institutional health summaries on resolution velocity, SLA compliance, and recurring hotspots.
- **Admin Automation Command Center (`/admin/automation`):** Live web dashboard to tune thresholds, toggle features, and trigger manual sweeps.

### 3. Staff & Administrative Workspace
- **Staff Queue:** Workload visibility, status transitions (`In Progress`, `Resolved`, `Rejected`), and audited remarks.
- **Knowledge Base (`/kb`):** Searchable student self-service guides for deflecting common inquiries.
- **Campus Notice Board (`/announcements`):** Official institutional bulletins and automated campus advisories.
- **Analytics & Exports:** Real-time Chart.js dashboards, styled Excel `.xlsx` spreadsheets (`openpyxl`), and printable compliance PDF views.

---

## Quick Start (Local Setup)

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/HarshMoradiya111/Grievance360.git
cd Grievance360
python -m pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the example environment template to `.env`:
```bash
cp .env.example .env
```
Open `.env` and configure your credentials:
```env
MONGO_URI="mongodb+srv://<username>:<password>@cluster0.mongodb.net/?appName=Cluster0"
MONGO_DB="grievance360"
SECRET_KEY="your-secret-key-here"

# Email Dispatch (Optional)
MAIL_ENABLED="True"
MAIL_SMTP="smtp.gmail.com"
MAIL_PORT="587"
MAIL_USER="your-email@gmail.com"
MAIL_PASSWORD="your-16-char-google-app-password"
MAIL_FROM="Grievance360 — CHARUSAT <your-email@gmail.com>"
PORTAL_URL="http://127.0.0.1:5000"
```

### 3. Initialize Database & Seed Accounts
```bash
python init_db.py
```

### 4. Run the Application
```bash
python app.py
```
Open your browser and navigate to: **http://127.0.0.1:5000**

---

## Demonstration Login Accounts

| Role | Email | Password | Access Scope |
|---|---|---|---|
| **Administrator** | `admin@grievance360.edu` | `admin123` | Full system governance, automation center & analytics |
| **Staff (IT Support)** | `it.staff@grievance360.edu` | `staff123` | Department assigned grievance queue & status updates |
| **Staff (Maintenance)** | `maintenance.staff@grievance360.edu` | `staff123` | Maintenance grievance queue |
| **Staff (Academics)** | `academics.staff@grievance360.edu` | `staff123` | Academic grievance queue |
| **Staff (Hostel)** | `hostel.staff@grievance360.edu` | `staff123` | Hostel facility grievance queue |
| **Student** | `harsh@student.edu` | `student123` | Student dashboard, raise grievance & tracking |
| **Student** | `priya@student.edu` | `student123` | Student dashboard & tracking |

*Students can also self-register for an account via `/register`.*

---

## Core Mathematical Algorithms

### 1. Dynamic Priority Scoring
```
Priority Score = (Category_Weight × 10)
               + (Age_In_Days × 2)
               + (Reopen_Count × 5)
               + (Supporter_Count × 2)
```
- **Category Weight (1–5):** Ensures high-impact issues take precedence immediately.
- **Age Factor:** Prevents starvation of older, low-priority issues.
- **Emergency Override:** Emergency/ragging complaints immediately bypass formula calculation with a fixed score of `100`.

### 2. SLA Elapsed Ratio & Escalation Window
```
Elapsed Ratio = (Current_Time - Created_Time) / (Deadline_Time - Created_Time)
```
- **Elapsed Ratio $\ge$ 0.75:** Dispatches proactive SLA Pre-Breach Early Warning to assigned staff.
- **Elapsed Ratio $\ge$ 1.00:** Declares SLA breach and auto-escalates to the next administrative tier.

### 3. Jaccard Text Token Similarity
```
J(A, B) = |Tokens(A) ∩ Tokens(B)| / |Tokens(A) ∪ Tokens(B)|
```
- When $J(A, B) \ge 0.50$ across complaints within the same category, the new ticket is linked as a duplicate and the submitter is added as a supporter.

---

## Project Structure

```
Grievance360/
├── app.py                  # All HTTP route definitions, role guards & controllers
├── automation.py           # Intelligent Automation Engine (12 autonomous systems)
├── scheduler.py            # Thread-safe periodic background sweep daemon
├── config.py               # Environment configuration & .env auto-loader
├── db.py                   # MongoDB Atlas cluster pool & SQL dual-engine shim
├── helpers.py              # Algorithmic business logic (Priority, SLA, Ticket codes)
├── init_db.py              # Database initialization & default seeder
├── mail.py                 # Multi-channel notification engine (SMTP + HTML templates)
├── requirements.txt        # Python package dependencies
├── .env.example            # Environment variables template
├── database/               # Database schemas and seed scripts
├── static/
│   ├── css/style.css       # Unified responsive styles & dark mode tokens
│   ├── js/track.js         # Real-time status polling (5s)
│   ├── js/notify.js        # Notification bell polling (15s)
│   └── js/charts.js        # Chart.js analytics visualizations
└── templates/              # Jinja2 responsive templates (Bootstrap 5.3)
    ├── base.html           # Master layout with responsive mobile navigation
    ├── admin/              # Administrator dashboards, automation center & reports
    ├── staff/              # Faculty investigation queues & update modals
    ├── student/            # Grievance filing, tracking & knowledge base
    └── partials/           # Reusable UI macros
```

---

## Security & Verification Standards

- **Salted Password Hashing:** PBKDF2 with SHA-256 via Werkzeug.
- **Two-Stage Authorization:** Role-based gating (`@role_required`) paired with record ownership checks (`can_view()`).
- **Cryptographic Reset Tokens:** Single-use 32-byte URL-safe reset tokens with 60-minute expiry.
- **SQL / NoSQL Injection Defense:** Parameterized queries for SQL and typed dictionary expressions for PyMongo.
- **Credential Protection:** Zero hardcoded credentials in tracked code; all secrets isolated in untracked `.env`.

---

## License

Developed as an academic software engineering project for higher education institutions. Released under the MIT License.
