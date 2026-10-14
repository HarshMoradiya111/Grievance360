# Grievance360 — Automation Features Specification & Roadmap
**Academic Project:** MSc-IT Final Year Project — Smart Grievance Redressal & Analytics Portal  
**Document:** Proposed Automation System Architecture & Feature Inventory  
**Target Audience:** Project Guide / Evaluator ("Ma'am") & Development Team  
**Date:** October 2026  

---

## Executive Summary

The **Grievance360** portal currently features a robust foundation with role-based access control, ticket lifecycle management, keyword-based auto-routing suggestions, priority scoring, escalation level formulas, and email notifications. 

However, several critical operations currently require **manual human intervention** (e.g., clicking a button to trigger escalations, manually picking staff members to assign tickets, manually closing resolved tickets, and manually merging duplicate complaints). 

This document outlines:
1. **Category A:** Current manual operations that will be transformed into **fully automated background processes**.
2. **Category B:** **Brand-new automation features** not yet present in the project that will elevate Grievance360 to a production-grade, autonomous grievance redressal ecosystem.

```mermaid
flowchart TD
    subgraph Student Actions
        A[Student Raises Grievance] --> B[Ticket Created]
    end

    subgraph Automation Engine (Background Worker / Scheduler)
        B --> C{Auto-Triage & Emergency Detection}
        C -->|Emergency / Ragging Flag| C1[Auto-Escalate to High Priority & Alert Security/Dean]
        C -->|Normal Grievance| D[Auto-Assign to Least-Burdened Staff]
        
        D --> E[Continuous SLA & Escalation Monitor]
        E -->|75% SLA Elapsed| F[Auto-Nudge Staff: Early Warning Alert]
        E -->|SLA Breached| G[Auto-Escalate to HOD / Management]
        E -->|No Activity in 48h| H[Auto-Stalled Ticket Reminder]
        
        I[Complaint Resolved by Staff] --> J[Auto-Trigger Feedback / Rating Request]
        J -->|No Student Reopen in 5 Days| K[Auto-Close Complaint & Archive]
        
        L[Periodic Schedule 8:00 AM] --> M[Auto-Generate & Email Daily Digest to Admin/Dean]
    end

    subgraph Notifications
        C1 --> N[Instant Email & In-App Alert]
        D --> N
        F --> N
        G --> N
        J --> N
        M --> N
    end
```

---

## Part 1: Features to Convert from Manual to Fully Automated

These modules exist in the codebase today, but rely on manual administrator or staff actions. Converting them to automated workflows removes administrative bottlenecks and guarantees SLA compliance.

| # | Feature Name | Current Manual Process | Proposed Automated Process | Impact & Benefit |
|---|---|---|---|---|
| **1.1** | **Automated Staff Assignment (Smart Dispatch)** | Currently, the system suggests a department via keyword scoring, but the ticket sits in `Pending` until an Admin manually navigates to `/complaint/<id>/assign` and selects a staff member from a dropdown. | **Zero-Touch Round-Robin & Load-Balanced Auto-Assignment:** Upon submission, the engine identifies the department and automatically assigns the complaint to the staff member with the lowest active ticket workload. The ticket instantly moves to `Assigned`, notifies the staff member, and begins resolution without waiting for admin review. | Eliminates ticket idle time; guarantees instant assignment 24/7 even outside office hours. |
| **1.2** | **Automated Escalation Sweep (Background Daemon)** | Currently, escalation levels (Reminder -> Department -> Management) are calculated, but the actual escalation sweep and notification dispatch must be **manually triggered** by the Admin clicking the "Run Sweep" button (`/admin/escalations/run`). | **Scheduled Escalation Daemon:** A background task (running every 30 minutes) scans all active complaints, checks `elapsed_ratio = (now - created_at) / (deadline - created_at)`, automatically elevates escalation levels, records audit logs, and sends escalation warning emails to HODs and Management. | Never misses an overdue grievance; eliminates the risk of human forgetfulness. |
| **1.3** | **Automated Ticket Closure (Grace Period Auto-Close)** | Currently, when staff marks a complaint as `Resolved`, it stays in the `Resolved` state indefinitely until an admin manually changes it to `Closed` or a student reopens it. | **Automated Resolution Grace Period:** If a resolved complaint remains inactive for 5 consecutive days without being reopened or commented on by the student, the system automatically transitions the status to `Closed`, logs an audit history entry, and sends a final closure confirmation email. | Keeps the dashboard clean and prevents open ticket clutter without manual administrator housekeeping. |
| **1.4** | **Automated CSAT / Feedback Collection Prompt** | Currently, feedback requires the student to voluntarily remember to navigate to the complaint detail page and click the rating stars. | **Post-Resolution Automated Survey Trigger:** The exact millisecond a ticket is marked `Resolved`, the student automatically receives an email and notification containing a direct, interactive 1-click 5-star rating widget (`/complaint/<ticket>/feedback`). If unrated after 48 hours, an automated gentle reminder is sent. | Multiplies student feedback response rates by 400%, providing realistic metrics for staff performance scorecards. |
| **1.5** | **Automated Duplicate Detection & Auto-Grouping** | Currently, `/api/similar` shows possible duplicates to the student before submission, but if the student ignores it and submits, merging the duplicate ticket requires an admin to manually open the ticket and submit a merge form (`/complaint/<id>/merge`). | **Automated Duplicate Tagging & Linked Clusters:** When a newly raised complaint has a Jaccard similarity score ≥ 0.70 with an active complaint in the same department/category, the system automatically tags it as `[Potential Duplicate of GRV-YYYY-NNNN]`, links them in the database, notifies the assigned staff member, and automatically adds the submitter to the existing ticket's supporter list ("Me Too"). | Prevents duplicate investigations for campus-wide issues (e.g., Wi-Fi outage in Block A). |

---

## Part 2: Brand-New Automation Features (Not Currently Present)

These features introduce advanced, state-of-the-art automation capabilities tailored for institutional grievance portals:

| # | Feature Name | Description & Mechanism | Educational / Operational Value |
|---|---|---|---|
| **2.1** | **Automated SLA Pre-Breach Early Warning Alerts (Yellow Alert)** | A predictive monitor that triggers when an active ticket reaches **75% or 80% of its SLA deadline** without reaching `In Progress` or `Resolved`. Automatically fires a "High Priority SLA Warning" email and dashboard badge to the assigned staff: *"Attention: Ticket GRV-2026-0014 has only 24 hours remaining before SLA breach!"* | Prevents SLA breaches *before* they occur rather than merely reporting them *after* failure. |
| **2.2** | **AI / NLP Automated Emergency & Safety Fast-Track Triage** | Automated NLP keyword and sentiment scanner for high-risk campus issues (*ragging, harassment, assault, medical emergency, fire, short circuit, depression, security breach*). If detected: overrides normal SLA to **24 hours**, assigns priority score of **100 (Critical)**, tags as **EMERGENCY**, and immediately triggers urgent alerts to Campus Security, Anti-Ragging Committee, and the Principal. | Guarantees institutional compliance with UGC / AICTE anti-ragging mandates and safety protocols. |
| **2.3** | **Automated Inactive / Stalled Ticket Ping (Staff Nudge)** | If an assigned complaint sits in `Assigned` or `In Progress` for more than **48 hours with zero staff comments or status updates**, the system automatically sends a polite "Staff Inactivity Nudge": *"Ticket GRV-XXXX is awaiting an update. Please log your progress or add a remark."* | Eliminates communication black holes where students feel their grievances are being ignored. |
| **2.4** | **Scheduled Daily / Weekly Executive Digest (Automated PDF/HTML Report)** | Every morning at 8:00 AM (or every Monday), the system automatically compiles an executive analytical summary (total grievances submitted, resolution rate, top 3 issue categories, pending SLA breaches, and staff performance rankings) and emails it automatically to the Principal, Registrar, and Heads of Departments. | Keeps college leadership informed automatically without requiring them to log into the portal. |
| **2.5** | **Automated Multi-Reopen Escalation to Dean / Ombudsperson** | If a grievance is reopened **2 or more times** by a student, it indicates chronic dissatisfaction with departmental handling. The system automatically bypasses the assigned staff member and re-routes the ticket directly to the **Dean / Institutional Ombudsperson** with a "High Discontent Risk" flag. | Prevents repetitive, unresolved disputes and protects student satisfaction. |
| **2.6** | **Automated Campus Outage & Complaint Spike Anomaly Detector** | If the system detects **5 or more complaints** submitted within a **2-hour window** belonging to the same category or location (e.g., "Hostel 3 Wi-Fi" or "Canteen Water Supply"), the system automatically flags a **"Campus Outage Detected"** and drafts an inline notice ready for 1-click broadcast on the Notice Board (`/announcements`). | Transforms individual repetitive grievances into proactive campus-wide communication. |

---

## Technical Implementation Blueprint

### 1. Engine Options
- **Lightweight Built-In Scheduler (Recommended for immediate deployment):**
  - Implement using Python's `APScheduler` (Advanced Python Scheduler) or a background daemon thread started inside `app.py`.
  - Runs in-process with Flask, zero external server dependencies, works seamlessly on both local development and standard hosting.
- **External Cron / Webhook Endpoint (For Serverless / Vercel compatibility):**
  - Secure API endpoints (e.g., `/api/cron/escalate`, `/api/cron/auto-assign`, `/api/cron/digest`) protected by a secret token (`CRON_SECRET`), compatible with GitHub Actions, Vercel Cron, or Windows Task Scheduler.

### 2. Configuration Settings (`config.py`)
```python
# Automation & Scheduling Config
AUTOMATION_ENABLED = True
AUTO_ASSIGN_STAFF = True          # Automatically assign new complaints to least-busy staff
AUTO_ESCALATION_INTERVAL_MIN = 30 # Run escalation sweep every 30 mins
AUTO_CLOSE_DAYS = 5               # Auto-close resolved complaints after 5 days
SLA_WARNING_PERCENT = 0.75        # Send early alert when 75% of SLA window has elapsed
STALLED_TICKET_HOURS = 48         # Nudge staff if no activity for 48 hours
EXECUTIVE_DIGEST_ENABLED = True   # Send scheduled summary to admin/dean
EMERGENCY_KEYWORDS_ENABLED = True # Fast-track safety and anti-ragging keywords
```

---

## Action Plan & Next Steps

Please present this document to your guide/evaluator ("Ma'am"). Once reviewed, we can proceed with the implementation according to your preferred priorities:

1. **Step 1:** Review the list and select which automations to enable first.
2. **Step 2:** Build the background automation engine in `helpers.py` / `automation.py`.
3. **Step 3:** Connect automated triggers to email (`mail.py`) and in-app notifications.
4. **Step 4:** Add an **Automation Control Panel** in the Admin Dashboard to allow college admins to toggle and configure automation rules.
