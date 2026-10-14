# Grievance360 — Phase-Wise Automation Implementation Plan

> **Strategy:** Phase-by-phase implementation with mandatory local testing verification, followed by git commit and push to GitHub before advancing to the next phase.

**Goal:** Transform Grievance360 into a fully automated grievance redressal ecosystem by converting current manual workflows into automated background jobs and implementing institutional-grade proactive automation features.

**Architecture:** 
- A modular Automation Engine (`automation.py`) containing deterministic rule-based algorithms (load-balanced assignment, NLP emergency triage, anomaly spike detection, SLA early warning, and auto-closure).
- A unified scheduling runner (`scheduler.py`) capable of running both as a local in-process background thread (`APScheduler`/threading) and as authenticated HTTP cron endpoints (`/api/cron/...`) for cloud/serverless deployments.
- Integration hooks into `app.py`, `helpers.py`, `mail.py`, and MongoDB/SQLite collections.
- An Admin Automation Control Center (`/admin/automation`) to configure rules and view automated execution logs.

**Tech Stack:** Python 3.x, Flask 3.1, PyMongo / SQLite shim, Bootstrap 5.3, SMTP / Resend API.

---

## Phase Breakdown Overview

| Phase | Focus Area | Features Included | Verification Gate |
|---|---|---|---|
| **Phase 1** | **Submission-Time Intelligent Dispatch & Triage** | • Auto-Assignment to Least-Burdened Staff<br>• AI/NLP Emergency & Anti-Ragging Fast-Track<br>• Automated Duplicate Tagging & Supporter Linking | Automated unit & integration tests on ticket submission |
| **Phase 2** | **Continuous Lifecycle & SLA Monitoring** | • Scheduled Escalation Daemon (replaces manual sweep)<br>• SLA Pre-Breach Early Warning (75% threshold)<br>• Automated Stalled Ticket Inactivity Nudge | Automated test suite verifying timed triggers and escalations |
| **Phase 3** | **Post-Resolution & Reopen Protection** | • Auto-Closure after 5-day grace period<br>• Automated 1-Click CSAT Feedback Survey Trigger<br>• Multi-Reopen Escalation to Dean / Ombudsperson | Automated lifecycle progression and rating tests |
| **Phase 4** | **Campus Intelligence & Admin Control Panel** | • Campus Outage & Complaint Spike Anomaly Detector<br>• Scheduled Executive Analytics Digest (Daily 8 AM)<br>• Admin Automation Settings & Logs Dashboard | End-to-end admin configuration & digest generation test |

---

## Detailed Phase Tasks & Execution Steps

### Phase 1: Submission-Time Intelligent Dispatch & Triage

#### Task 1.1: Core Automation Dispatch Module (`automation.py`)
- **Files:**
  - Create: `automation.py`
  - Modify: `config.py` (add automation configuration flags)
- **Features implemented:**
  1. `auto_assign_complaint(complaint_id)`: Queries active staff members in the assigned department, calculates current active workload (`status NOT IN ('Resolved', 'Closed', 'Rejected')`), and assigns to the staff member with the lowest load (with round-robin tiebreaker).
  2. `detect_emergency_triage(subject, description)`: Scans for critical safety keywords (*ragging, harassment, abuse, assault, fire, electric shock, medical emergency, suicide, violence*). If detected:
     - Sets `is_emergency = True`
     - Overrides SLA deadline to 24 hours
     - Sets priority score to 100 (`Critical`)
     - Tags complaint as `[EMERGENCY_FAST_TRACK]`
  3. `check_and_tag_duplicate(complaint_id, subject, description, category_id, user_id)`: If Jaccard similarity $\ge 0.70$ against an open complaint in the same category, tags `duplicate_of_id`, links complaints, and automatically adds the submitter to the supporter list.

#### Task 1.2: Integrate Phase 1 into Complaint Submission Flow
- **Files:**
  - Modify: `app.py` (route `/complaint/new` and helper routines)
  - Modify: `mail.py` (add emergency alert email to Security/Dean)
- **Workflow:**
  - When student submits `/complaint/new`:
    1. Run emergency scan. If flagged, mark emergency, bump priority to 100, and fire emergency notification to Admins, Security, and Dean.
    2. Run duplicate check. If duplicate found, tag and link automatically.
    3. Run auto-assigner. Find least-burdened staff, update status from `Pending` $\to$ `Assigned`, log history, and notify student + assigned staff.

#### Task 1.3: Local Testing & Verification (Phase 1 Gate)
- **Test Script:** `test_phase1_automation.py`
  - Test Case 1: Submit normal complaint $\to$ verify status is immediately `Assigned`, staff with lowest workload is selected, and assignment audit log exists.
  - Test Case 2: Submit complaint with keyword "ragging in hostel" $\to$ verify priority score is 100, deadline is 24h, emergency flag is True.
  - Test Case 3: Submit complaint identical to existing open complaint $\to$ verify auto-duplicate tag and linkage.
- **Execution:** `python test_phase1_automation.py`
- **Git Push Gate:**
  ```bash
  git add config.py automation.py app.py mail.py test_phase1_automation.py
  git commit -m "feat(automation): Phase 1 - Auto-assignment, emergency triage, and duplicate linking"
  git push origin master
  ```

---

### Phase 2: Continuous Lifecycle & SLA Monitoring (Escalation Daemon)

#### Task 2.1: Lifecycle Background Engine (`automation.py`)
- **Features implemented:**
  1. `run_automated_escalations()`: Evaluates all open complaints, calculates `elapsed_ratio`, checks thresholds (0.5, 1.0, 2.0), advances level, records escalation record, and sends email/in-app notification (converts the manual `/admin/escalations/run` into an automated engine).
  2. `check_sla_pre_breach_warnings()`: Identifies tickets at $\ge 75\%$ of SLA deadline still in `Pending` or `Assigned`. Fired warning notifications to staff and department head.
  3. `check_stalled_complaints()`: Finds tickets in `Assigned` or `In Progress` with no updates or comments for $> 48$ hours. Sends staff inactivity nudge.

#### Task 2.2: Scheduled Runner & Cron Endpoints
- **Files:**
  - Create: `scheduler.py` (background thread loop running periodically)
  - Modify: `app.py` (add secure cron endpoint `/api/cron/lifecycle-sweep` for deployment environments)
  - Modify: `mail.py` (add pre-breach warning email and stalled nudge email)

#### Task 2.3: Local Testing & Verification (Phase 2 Gate)
- **Test Script:** `test_phase2_automation.py`
  - Test Case 1: Mock ticket past 50% SLA $\to$ run sweep $\to$ verify escalation level 1 recorded & notification generated.
  - Test Case 2: Mock ticket at 80% SLA $\to$ verify pre-breach early warning alert generated.
  - Test Case 3: Mock ticket idle for 50 hours $\to$ verify stalled nudge generated.
- **Execution:** `python test_phase2_automation.py`
- **Git Push Gate:**
  ```bash
  git add automation.py scheduler.py app.py mail.py test_phase2_automation.py
  git commit -m "feat(automation): Phase 2 - Background escalation daemon, SLA pre-breach alerts, and stalled nudges"
  git push origin master
  ```

---

### Phase 3: Post-Resolution & Reopen Protection

#### Task 3.1: Post-Resolution Automations
- **Features implemented:**
  1. `auto_close_resolved_complaints()`: Queries all complaints with status `Resolved` where `resolved_at <= now - 5 days` and no recent reopen/comments. Automatically transitions to `Closed`, logs audit entry, and sends closure notification.
  2. `trigger_post_resolution_survey(complaint_id)`: Hook called upon status transitioning to `Resolved`. Sends an automated email with direct 1-click 5-star rating link (`/complaint/<ticket>/feedback`).
  3. `handle_multi_reopen_escalation(complaint_id)`: If `reopen_count >= 2`, automatically updates escalation level to `Management`, flags as `Chronic Grievance / High Discontent`, and assigns directly to Principal / Dean / Ombudsperson.

#### Task 3.2: Integrate Phase 3 into Routes & Templates
- **Files:**
  - Modify: `app.py` (hook into `update_status` and `reopen_complaint`)
  - Modify: `mail.py` (add interactive feedback prompt email and Dean multi-reopen alert)
  - Modify: `templates/student/track.html` (enhanced 1-click feedback widget)

#### Task 3.3: Local Testing & Verification (Phase 3 Gate)
- **Test Script:** `test_phase3_automation.py`
  - Test Case 1: Status update to `Resolved` $\to$ verify feedback email triggered.
  - Test Case 2: Mock ticket resolved 6 days ago $\to$ run auto-close $\to$ verify status transitions to `Closed`.
  - Test Case 3: Reopen ticket second time $\to$ verify auto-escalated to Dean/Ombudsperson.
- **Execution:** `python test_phase3_automation.py`
- **Git Push Gate:**
  ```bash
  git add automation.py app.py mail.py templates/ test_phase3_automation.py
  git commit -m "feat(automation): Phase 3 - Auto-close grace period, 1-click CSAT survey, and multi-reopen escalation"
  git push origin master
  ```

---

### Phase 4: Campus Intelligence & Admin Control Center

#### Task 4.1: Outage Detector & Scheduled Digest
- **Features implemented:**
  1. `detect_campus_outage_spike()`: Analyzes complaints submitted in the last 2 hours. If $\ge 5$ complaints belong to the same category/department, triggers a "Campus Outage Alert" and automatically prepares a draft notice in `announcements`.
  2. `generate_executive_digest()`: Aggregates daily/weekly metrics: new tickets, resolved count, SLA compliance %, top 3 problem categories, and staff scorecard summary. Formats into a clean branded email report sent to administrators.

#### Task 4.2: Admin Automation Control Center UI
- **Files:**
  - Create: `templates/admin/automation.html`
  - Modify: `app.py` (routes `/admin/automation`, `/admin/automation/toggle`, `/admin/automation/run-now`)
  - Features:
    - Live status toggles for each automation rule (Auto-Assignment, Escalation Daemon, Auto-Closure, Outage Detector, Executive Digest).
    - Manual "Trigger Now" buttons for testing each automation on demand.
    - Automation activity audit log showing the last 50 automated actions taken by the system.

#### Task 4.3: Local Testing & Verification (Phase 4 Gate)
- **Test Script:** `test_phase4_automation.py`
  - Test Case 1: Insert 5 complaints in 1 hour under same category $\to$ verify outage detection flag and draft announcement.
  - Test Case 2: Run digest generator $\to$ verify HTML executive report compiled without error.
  - Test Case 3: Test `/admin/automation` control panel toggles and trigger-now endpoints.
- **Execution:** `python test_phase4_automation.py`
- **Git Push Gate:**
  ```bash
  git add automation.py scheduler.py app.py templates/admin/automation.html test_phase4_automation.py
  git commit -m "feat(automation): Phase 4 - Campus outage detector, executive digest, and Admin Automation Center"
  git push origin master
  ```

---

## Progress Tracking Checklist

- [ ] **Phase 1: Submission-Time Intelligent Dispatch & Triage**
  - [ ] Auto-assignment to least-burdened staff
  - [ ] AI/NLP emergency & anti-ragging triage
  - [ ] Automated duplicate tagging & supporter linking
  - [ ] Local tests verified
  - [ ] Git commit & push
- [ ] **Phase 2: Continuous Lifecycle & SLA Monitoring**
  - [ ] Scheduled escalation daemon
  - [ ] SLA pre-breach early warning (75%)
  - [ ] Stalled ticket inactivity nudge
  - [ ] Local tests verified
  - [ ] Git commit & push
- [ ] **Phase 3: Post-Resolution & Reopen Protection**
  - [ ] 5-day grace period auto-closure
  - [ ] 1-click CSAT feedback trigger
  - [ ] Multi-reopen escalation to Dean
  - [ ] Local tests verified
  - [ ] Git commit & push
- [ ] **Phase 4: Campus Intelligence & Admin Control Panel**
  - [ ] Campus outage & spike anomaly detector
  - [ ] Scheduled executive email digest
  - [ ] Admin Automation Control Center UI
  - [ ] Local tests verified
  - [ ] Git commit & push
