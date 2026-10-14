"""
Grievance360 — Automation Engine.
Contains rule-based deterministic algorithms and background lifecycle workers:
  - Phase 1: Smart load-balanced auto-assignment, emergency triage, duplicate clustering.
  - Phase 2: Lifecycle escalation daemon, SLA pre-breach alerts, stalled nudges.
  - Phase 3: Auto-close grace period, CSAT feedback trigger, multi-reopen escalation.
  - Phase 4: Campus outage detector, executive digest.
"""

import logging
import re
from datetime import datetime, timedelta
from bson.objectid import ObjectId

import config
import helpers
import mail

log = logging.getLogger(__name__)

# Keywords that indicate severe safety, institutional, or physical emergency.
EMERGENCY_KEYWORDS = [
    "ragging", "harass", "molest", "abuse", "assault", "violence", "fight",
    "beating", "bully", "suicide", "suicidal", "kill", "depression", "threat",
    "blackmail", "weapon", "knife", "gun", "fire", "explosion", "short circuit",
    "electric shock", "gas leak", "poison", "hospital", "ambulance",
    "police", "fir", "theft", "stolen"
]


# ===========================================================================
# PHASE 1: SUBMISSION-TIME DISPATCH & TRIAGE
# ===========================================================================

def detect_emergency_triage(subject, description):
    """
    Scans subject and description for critical safety / emergency keywords.
    Matches root words (e.g. harass -> harassing, harassment; abuse -> abusing).
    Returns:
      is_emergency (bool), matched_keywords (list), reason (str)
    """
    if not getattr(config, "EMERGENCY_TRIAGE_ENABLED", True):
        return False, [], ""

    text = f"{subject or ''} {description or ''}".lower()
    matched = []
    for kw in EMERGENCY_KEYWORDS:
        pattern = r"\b" + re.escape(kw)
        if re.search(pattern, text):
            if kw not in matched:
                matched.append(kw)

    if matched:
        reason = f"Critical keywords detected: {', '.join(matched[:5])}"
        return True, matched, reason

    return False, [], ""


def auto_assign_staff(db_conn, department_id):
    """
    Finds the active staff member with the lowest active ticket workload
    in the specified department.
    Returns:
      dict with staff details or None if no staff available.
    """
    if not getattr(config, "AUTO_ASSIGN_ENABLED", True):
        return None

    if not department_id:
        return None

    dept_oid = ObjectId(department_id) if not isinstance(department_id, ObjectId) else department_id

    # 1. Query active staff members in this department
    staff_members = list(db_conn.users.find({
        "role": "staff",
        "department_id": dept_oid,
        "is_active": True
    }))

    # Fallback: if no staff in exact department, find any active staff
    if not staff_members:
        staff_members = list(db_conn.users.find({
            "role": "staff",
            "is_active": True
        }))

    if not staff_members:
        return None

    # 2. Count active workload for each staff member
    candidates = []
    closed_statuses = list(config.CLOSED_STATUSES)
    for staff in staff_members:
        active_count = db_conn.complaints.count_documents({
            "assigned_to": staff["_id"],
            "status": {"$nin": closed_statuses}
        })
        candidates.append({
            "id": str(staff["_id"]),
            "_id": staff["_id"],
            "name": staff.get("name", "Staff Member"),
            "email": staff.get("email"),
            "department_id": staff.get("department_id"),
            "active_count": active_count,
            "last_assigned_at": staff.get("last_assigned_at", "2000-01-01 00:00:00")
        })

    # 3. Sort: primary by lowest workload, secondary by least recently assigned
    candidates.sort(key=lambda s: (s["active_count"], s["last_assigned_at"]))
    chosen = candidates[0]

    # Update last_assigned_at timestamp on the chosen staff member
    db_conn.users.update_one(
        {"_id": chosen["_id"]},
        {"$set": {"last_assigned_at": helpers.now_str()}}
    )

    return chosen


def check_and_tag_duplicate(db_conn, subject, description, category_id, user_id, current_complaint_id=None):
    """
    Checks for high textual similarity with active open complaints.
    If similarity >= threshold (default 0.65), tags duplicate and links parent.
    Returns:
      is_duplicate (bool), parent_ticket_code (str or None), score (float)
    """
    if not getattr(config, "AUTO_DUPLICATE_LINK_ENABLED", True):
        return False, None, 0.0

    threshold = getattr(config, "DUPLICATE_SIMILARITY_THRESHOLD", 0.65)
    cat_oid = ObjectId(category_id) if (category_id and not isinstance(category_id, ObjectId)) else category_id
    u_oid = ObjectId(user_id) if (user_id and not isinstance(user_id, ObjectId)) else user_id
    c_oid = ObjectId(current_complaint_id) if (current_complaint_id and not isinstance(current_complaint_id, ObjectId)) else None

    query = {
        "status": {"$nin": list(config.CLOSED_STATUSES)}
    }
    if cat_oid:
        query["category_id"] = cat_oid
    if u_oid:
        query["user_id"] = {"$ne": u_oid}
    if c_oid:
        query["_id"] = {"$ne": c_oid}

    candidates = list(db_conn.complaints.find(query).sort("created_at", -1).limit(40))

    best_match = None
    best_score = 0.0

    for cand in candidates:
        score = helpers.similarity(subject, description, cand.get("subject", ""), cand.get("description", ""))
        if score > best_score:
            best_score = score
            best_match = cand

    if best_match and best_score >= threshold:
        return True, best_match.get("ticket_code"), round(best_score, 2), best_match["_id"]

    return False, None, round(best_score, 2), None


def process_new_complaint_automation(db_conn, complaint_id, app_context_url_builder=None):
    """
    Main entry point called immediately upon complaint submission.
    Executes:
      1. Emergency & Anti-Ragging Fast-Track Triage
      2. Duplicate Detection & Auto-Grouping
      3. Least-Burdened Staff Auto-Assignment
    Returns dict of actions taken.
    """
    c_oid = ObjectId(complaint_id) if not isinstance(complaint_id, ObjectId) else complaint_id
    complaint = db_conn.complaints.find_one({"_id": c_oid})
    if not complaint:
        return {"error": "Complaint not found"}

    actions = {
        "emergency_detected": False,
        "auto_assigned": False,
        "duplicate_tagged": False,
        "assigned_to": None,
        "logs": []
    }

    now = helpers.now_str()
    updates = {"updated_at": now}

    # -----------------------------------------------------------------------
    # Step 1: Emergency & Anti-Ragging Triage
    # -----------------------------------------------------------------------
    is_emergency, keywords, reason = detect_emergency_triage(
        complaint.get("subject"), complaint.get("description")
    )
    if is_emergency:
        actions["emergency_detected"] = True
        actions["logs"].append(f"Emergency Fast-Track triggered ({reason})")

        emergency_deadline = helpers.add_days(now, getattr(config, "EMERGENCY_SLA_DAYS", 1))
        updates["is_emergency"] = True
        updates["emergency_keywords"] = keywords
        updates["priority_score"] = 100
        updates["deadline"] = emergency_deadline
        updates["tags"] = list(set(complaint.get("tags", []) + ["EMERGENCY", "FAST_TRACK"]))

        # Log emergency to status history
        db_conn.complaint_status_history.insert_one({
            "complaint_id": c_oid,
            "old_status": complaint.get("status"),
            "new_status": complaint.get("status"),
            "remark": f"AUTOMATION: High-Priority Emergency Triage activated. {reason}",
            "changed_by": None,
            "is_automated": True,
            "created_at": now
        })

        # Alert all admins and security immediately
        admins = list(db_conn.users.find({"role": "admin"}))
        for admin in admins:
            track_url = f"/complaint/{complaint.get('ticket_code')}"
            db_conn.notifications.insert_one({
                "user_id": admin["_id"],
                "message": f"🚨 EMERGENCY ALERT {complaint.get('ticket_code')}: {complaint.get('subject')[:40]}",
                "link": track_url,
                "is_read": False,
                "created_at": now
            })
            if admin.get("email"):
                mail.send_async(
                    admin["email"],
                    f"[EMERGENCY ALERT] {complaint.get('ticket_code')} — Immediate Attention Required",
                    f"<p>An urgent emergency grievance was flagged by the automated triage system.</p>"
                    f"<p><strong>Ticket:</strong> {complaint.get('ticket_code')}<br>"
                    f"<strong>Subject:</strong> {complaint.get('subject')}<br>"
                    f"<strong>Matched Keywords:</strong> {', '.join(keywords)}<br>"
                    f"<strong>Action:</strong> SLA deadline set to 24 hours.</p>"
                )

    # -----------------------------------------------------------------------
    # Step 2: Duplicate Detection & Linking
    # -----------------------------------------------------------------------
    is_dup, parent_ticket, dup_score, parent_id = check_and_tag_duplicate(
        db_conn,
        complaint.get("subject"),
        complaint.get("description"),
        complaint.get("category_id"),
        complaint.get("user_id"),
        current_complaint_id=c_oid
    )
    if is_dup and parent_id:
        actions["duplicate_tagged"] = True
        actions["logs"].append(f"Auto-linked as duplicate of {parent_ticket} (Similarity: {int(dup_score * 100)}%)")
        updates["is_duplicate"] = True
        updates["duplicate_of_ticket"] = parent_ticket
        updates["duplicate_of_id"] = parent_id
        updates["similarity_score"] = dup_score

        # Add submitter as supporter on parent ticket to boost parent priority
        db_conn.complaints.update_one(
            {"_id": parent_id},
            {
                "$addToSet": {"supporters": complaint.get("user_id")},
                "$inc": {"supporter_count": 1}
            }
        )

        db_conn.complaint_status_history.insert_one({
            "complaint_id": c_oid,
            "old_status": complaint.get("status"),
            "new_status": complaint.get("status"),
            "remark": f"AUTOMATION: Identified as {int(dup_score * 100)}% similar to open complaint {parent_ticket}. Automatically linked.",
            "changed_by": None,
            "is_automated": True,
            "created_at": now
        })

    # -----------------------------------------------------------------------
    # Step 3: Least-Burdened Staff Auto-Assignment
    # -----------------------------------------------------------------------
    assigned_staff = auto_assign_staff(db_conn, complaint.get("department_id"))
    if assigned_staff:
        actions["auto_assigned"] = True
        actions["assigned_to"] = assigned_staff["name"]
        actions["logs"].append(f"Assigned to {assigned_staff['name']} (Active Workload: {assigned_staff['active_count']} tickets)")

        updates["assigned_to"] = assigned_staff["_id"]
        updates["status"] = "Assigned"
        updates["assigned_at"] = now

        # Add status history for assignment
        db_conn.complaint_status_history.insert_one({
            "complaint_id": c_oid,
            "old_status": complaint.get("status"),
            "new_status": "Assigned",
            "remark": f"AUTOMATION: Smart Dispatch auto-assigned to {assigned_staff['name']} (Workload: {assigned_staff['active_count']} active tickets).",
            "changed_by": None,
            "is_automated": True,
            "created_at": now
        })

        # Notify assigned staff
        track_url = f"/complaint/{complaint.get('ticket_code')}"
        db_conn.notifications.insert_one({
            "user_id": assigned_staff["_id"],
            "message": f"New ticket auto-assigned: {complaint.get('ticket_code')} ({complaint.get('subject')[:40]})",
            "link": track_url,
            "is_read": False,
            "created_at": now
        })

        # Email student that ticket is assigned
        student = db_conn.users.find_one({"_id": complaint.get("user_id")})
        dept = db_conn.departments.find_one({"_id": complaint.get("department_id")})
        if student and student.get("email"):
            mail.notify_complaint_assigned(
                student_email=student["email"],
                student_name=student.get("name", "Student"),
                ticket_code=complaint.get("ticket_code"),
                department=dept.get("name") if dept else "General",
                assigned_to_name=assigned_staff["name"]
            )

    # Commit updates to MongoDB
    db_conn.complaints.update_one({"_id": c_oid}, {"$set": updates})

    return actions


# ===========================================================================
# PHASE 2: CONTINUOUS LIFECYCLE & SLA MONITORING (ESCALATION DAEMON)
# ===========================================================================

def run_automated_escalations(db_conn):
    """
    Background worker that scans all open complaints, calculates elapsed SLA ratio,
    and automatically advances escalation levels (Reminder -> Department -> Management).
    Replaces the manual 'Run Sweep' admin button.
    """
    if not getattr(config, "AUTO_ESCALATION_ENABLED", True):
        return {"skipped": True, "reason": "AUTO_ESCALATION_ENABLED is False"}

    closed_statuses = list(config.CLOSED_STATUSES)
    open_complaints = list(db_conn.complaints.find({
        "status": {"$nin": closed_statuses}
    }))

    admins = list(db_conn.users.find({"role": "admin"}))
    raised = 0
    now = helpers.now_str()

    for c in open_complaints:
        lvl, label, _ = helpers.escalation_level(c)
        if lvl == 0:
            continue

        # Look up current highest recorded escalation level
        existing = db_conn.escalations.find_one(
            {"complaint_id": c["_id"]},
            sort=[("to_level", -1)]
        )
        current_top = existing.get("to_level", 0) if existing else 0
        if lvl <= current_top:
            continue  # Escalation only moves up

        ratio = helpers.elapsed_ratio(c)
        reason = f"Elapsed ratio {ratio:.2f} — {label} threshold reached."

        # Notify assigned staff for Level 1, all admins + staff for Level 2+
        notify_users = []
        if lvl == 1 and c.get("assigned_to"):
            staff_user = db_conn.users.find_one({"_id": c["assigned_to"]})
            if staff_user:
                notify_users.append(staff_user)
        elif lvl >= 2:
            notify_users.extend(admins)
            if c.get("assigned_to"):
                staff_user = db_conn.users.find_one({"_id": c["assigned_to"]})
                if staff_user and staff_user not in notify_users:
                    notify_users.append(staff_user)

        # Record escalation
        for u in notify_users:
            db_conn.escalations.insert_one({
                "complaint_id": c["_id"],
                "from_level": current_top,
                "to_level": lvl,
                "reason": reason,
                "notified_user_id": u["_id"],
                "is_automated": True,
                "escalated_at": now
            })

            # In-app notification
            track_url = f"/complaint/{c.get('ticket_code')}"
            db_conn.notifications.insert_one({
                "user_id": u["_id"],
                "message": f"⚡ Ticket {c.get('ticket_code')} auto-escalated to {label} level.",
                "link": track_url,
                "is_read": False,
                "created_at": now
            })

            # Email notification
            if u.get("email"):
                mail.notify_escalation(
                    admin_email=u["email"],
                    ticket_code=c.get("ticket_code", "TICKET"),
                    subject=c.get("subject", "No subject"),
                    level_label=label,
                    student_name="Student",
                    portal_base=config.PORTAL_URL
                )

        # Audit trail history
        db_conn.complaint_status_history.insert_one({
            "complaint_id": c["_id"],
            "old_status": c.get("status"),
            "new_status": c.get("status"),
            "remark": f"AUTOMATION DAEMON: Ticket auto-escalated to {label} (Level {lvl}). {reason}",
            "changed_by": None,
            "is_automated": True,
            "created_at": now
        })

        db_conn.complaints.update_one(
            {"_id": c["_id"]},
            {"$set": {"escalation_level": lvl, "updated_at": now}}
        )
        raised += 1

    return {"checked": len(open_complaints), "escalated": raised}


def check_sla_pre_breach_warnings(db_conn):
    """
    Early Warning System (Yellow Alert):
    Detects complaints that have consumed >= 75% of their allowed SLA time
    and warns assigned staff before the breach occurs.
    """
    threshold = getattr(config, "SLA_WARNING_PERCENT", 0.75)
    closed_statuses = list(config.CLOSED_STATUSES)

    open_complaints = list(db_conn.complaints.find({
        "status": {"$nin": closed_statuses},
        "pre_breach_warned": {"$ne": True}
    }))

    now = helpers.now_str()
    warned = 0

    for c in open_complaints:
        ratio = helpers.elapsed_ratio(c)
        if ratio >= threshold and ratio < 1.0:
            warned += 1
            db_conn.complaints.update_one(
                {"_id": c["_id"]},
                {"$set": {"pre_breach_warned": True, "updated_at": now}}
            )

            # Audit history entry
            pct = int(ratio * 100)
            db_conn.complaint_status_history.insert_one({
                "complaint_id": c["_id"],
                "old_status": c.get("status"),
                "new_status": c.get("status"),
                "remark": f"AUTOMATION: SLA Pre-Breach Early Warning triggered ({pct}% elapsed time).",
                "changed_by": None,
                "is_automated": True,
                "created_at": now
            })

            # Notify assigned staff
            if c.get("assigned_to"):
                track_url = f"/complaint/{c.get('ticket_code')}"
                db_conn.notifications.insert_one({
                    "user_id": c["assigned_to"],
                    "message": f"⚠️ SLA Early Warning: {c.get('ticket_code')} has used {pct}% of SLA time!",
                    "link": track_url,
                    "is_read": False,
                    "created_at": now
                })
                staff_user = db_conn.users.find_one({"_id": c["assigned_to"]})
                if staff_user and staff_user.get("email"):
                    mail.send_async(
                        staff_user["email"],
                        f"[SLA Early Warning] {c.get('ticket_code')} is at {pct}% SLA limit",
                        f"<p>Attention <strong>{staff_user.get('name')}</strong>,</p>"
                        f"<p>Ticket <strong>{c.get('ticket_code')}</strong> ({c.get('subject')}) "
                        f"has consumed <strong>{pct}%</strong> of its allowed SLA window.</p>"
                        f"<p>Please review and resolve this complaint promptly to prevent an institutional SLA breach.</p>"
                    )

    return {"checked": len(open_complaints), "pre_breach_warned": warned}


def check_stalled_complaints(db_conn):
    """
    Inactivity Nudge:
    Finds complaints in 'Assigned' or 'In Progress' with no status change
    or comments for over STALLED_TICKET_HOURS (default 48h).
    """
    stall_hours = getattr(config, "STALLED_TICKET_HOURS", 48)
    now = helpers.now_str()
    now_dt = datetime.now()

    stalled_candidates = list(db_conn.complaints.find({
        "status": {"$in": ["Assigned", "In Progress"]}
    }))

    nudged = 0
    for c in stalled_candidates:
        # Check last update or last nudge
        last_dt = helpers.to_dt(c.get("last_stalled_nudge_at") or c.get("updated_at") or c.get("created_at"))
        if not last_dt:
            continue

        hours_elapsed = (now_dt - last_dt).total_seconds() / 3600.0
        if hours_elapsed >= stall_hours:
            nudged += 1
            db_conn.complaints.update_one(
                {"_id": c["_id"]},
                {"$set": {"last_stalled_nudge_at": now, "updated_at": now}}
            )

            # Audit history entry
            db_conn.complaint_status_history.insert_one({
                "complaint_id": c["_id"],
                "old_status": c.get("status"),
                "new_status": c.get("status"),
                "remark": f"AUTOMATION: Stalled ticket reminder dispatched ({int(hours_elapsed)} hours without activity).",
                "changed_by": None,
                "is_automated": True,
                "created_at": now
            })

            # Notify assigned staff
            if c.get("assigned_to"):
                track_url = f"/complaint/{c.get('ticket_code')}"
                db_conn.notifications.insert_one({
                    "user_id": c["assigned_to"],
                    "message": f"⏰ Inactivity Nudge: Ticket {c.get('ticket_code')} has been stalled for {int(hours_elapsed)}h. Please post an update.",
                    "link": track_url,
                    "is_read": False,
                    "created_at": now
                })

    return {"checked": len(stalled_candidates), "nudged": nudged}


def run_lifecycle_sweep(db_conn):
    """
    Consolidated runner that executes all lifecycle automation routines:
      - Phase 2: Escalations, SLA early warnings, stalled ticket nudges.
      - Phase 3: 5-day grace period auto-closure of resolved tickets.
    """
    esc_result = run_automated_escalations(db_conn)
    sla_result = check_sla_pre_breach_warnings(db_conn)
    stall_result = check_stalled_complaints(db_conn)
    autoclose_result = auto_close_resolved_complaints(db_conn)

    return {
        "timestamp": helpers.now_str(),
        "escalations": esc_result,
        "sla_warnings": sla_result,
        "stalled_nudges": stall_result,
        "auto_closures": autoclose_result
    }


# ===========================================================================
# PHASE 3: POST-RESOLUTION & REOPEN PROTECTION
# ===========================================================================

def auto_close_resolved_complaints(db_conn):
    """
    Grace Period Auto-Closure:
    If a ticket remains 'Resolved' for AUTO_CLOSE_DAYS (default 5 days)
    without student reopen or comment, automatically transitions to 'Closed'.
    """
    grace_days = getattr(config, "AUTO_CLOSE_DAYS", 5)
    now_dt = datetime.now()
    cutoff_dt = now_dt - timedelta(days=grace_days)
    cutoff_str = cutoff_dt.strftime(helpers.DT_FORMAT)
    now_str = helpers.now_str()

    resolved_tickets = list(db_conn.complaints.find({
        "status": "Resolved",
        "resolved_at": {"$lte": cutoff_str}
    }))

    closed_count = 0
    for c in resolved_tickets:
        closed_count += 1
        db_conn.complaints.update_one(
            {"_id": c["_id"]},
            {"$set": {
                "status": "Closed",
                "auto_closed_at": now_str,
                "updated_at": now_str
            }}
        )

        # Audit trail history
        db_conn.complaint_status_history.insert_one({
            "complaint_id": c["_id"],
            "old_status": "Resolved",
            "new_status": "Closed",
            "remark": f"AUTOMATION: Automatically closed after {grace_days}-day resolution grace period.",
            "changed_by": None,
            "is_automated": True,
            "created_at": now_str
        })

        # Notify student
        track_url = f"/complaint/{c.get('ticket_code')}"
        db_conn.notifications.insert_one({
            "user_id": c["user_id"],
            "message": f"🔒 Ticket {c.get('ticket_code')} has been closed after the {grace_days}-day resolution grace period.",
            "link": track_url,
            "is_read": False,
            "created_at": now_str
        })

        # Email student closure confirmation
        student = db_conn.users.find_one({"_id": c["user_id"]})
        if student and student.get("email"):
            mail.send_async(
                student["email"],
                f"[Ticket Closed] {c.get('ticket_code')} — Resolution Finalized",
                f"<p>Dear <strong>{student.get('name', 'Student')}</strong>,</p>"
                f"<p>Your complaint <strong>{c.get('ticket_code')}</strong> ({c.get('subject')}) "
                f"has been automatically marked <strong>Closed</strong> following the {grace_days}-day resolution period.</p>"
                f"<p>Thank you for using the Grievance360 portal.</p>"
            )

    return {"checked": len(resolved_tickets), "auto_closed": closed_count}


def trigger_post_resolution_feedback(db_conn, complaint_id):
    """
    Automated CSAT / Feedback Survey Prompt:
    Fires the moment a complaint transitions to 'Resolved'.
    Dispatches an in-app prompt and email with a direct 1-click rating link.
    """
    c_oid = ObjectId(complaint_id) if not isinstance(complaint_id, ObjectId) else complaint_id
    complaint = db_conn.complaints.find_one({"_id": c_oid})
    if not complaint:
        return False

    now_str = helpers.now_str()

    # Check if feedback was already provided
    existing_fb = db_conn.feedback.find_one({"complaint_id": c_oid})
    if existing_fb:
        return False

    db_conn.complaints.update_one(
        {"_id": c_oid},
        {"$set": {"feedback_requested": True, "feedback_requested_at": now_str}}
    )

    track_url = f"/complaint/{complaint.get('ticket_code')}"

    # In-app notification with rating prompt
    db_conn.notifications.insert_one({
        "user_id": complaint["user_id"],
        "message": f"🌟 Please rate your experience! Your complaint {complaint.get('ticket_code')} has been resolved.",
        "link": track_url,
        "is_read": False,
        "created_at": now_str
    })

    # Status history log
    db_conn.complaint_status_history.insert_one({
        "complaint_id": c_oid,
        "old_status": complaint.get("status"),
        "new_status": complaint.get("status"),
        "remark": "AUTOMATION: Post-resolution feedback survey triggered to student.",
        "changed_by": None,
        "is_automated": True,
        "created_at": now_str
    })

    # Branded interactive feedback email
    student = db_conn.users.find_one({"_id": complaint["user_id"]})
    if student and student.get("email"):
        portal_base = getattr(config, "PORTAL_URL", "https://grievance360portal.vercel.app")
        survey_link = f"{portal_base}/complaint/{complaint.get('ticket_code')}"
        mail.send_async(
            student["email"],
            f"[Rate Resolution] How did we do with ticket {complaint.get('ticket_code')}?",
            f"<p>Dear <strong>{student.get('name', 'Student')}</strong>,</p>"
            f"<p>Your complaint <strong>{complaint.get('ticket_code')}</strong> has been marked as <strong>Resolved</strong>.</p>"
            f"<p>Please take 10 seconds to share your feedback. Your rating helps evaluate institutional staff performance:</p>"
            f"<p style='text-align:center;margin:24px 0'>"
            f"<a href='{survey_link}' style='background:#5b6ea8;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600'>"
            f"⭐ Submit Star Rating & Feedback</a></p>"
        )

    return True


def handle_multi_reopen_escalation(db_conn, complaint_id, student_id):
    """
    Chronic Grievance / High Dissatisfaction Protection:
    If a grievance is reopened 2 or more times, it bypasses departmental staff
    and automatically escalates to Level 3 (Principal / Dean / Ombudsperson).
    """
    c_oid = ObjectId(complaint_id) if not isinstance(complaint_id, ObjectId) else complaint_id
    complaint = db_conn.complaints.find_one({"_id": c_oid})
    if not complaint:
        return False

    reopen_count = complaint.get("reopen_count", 0)
    if reopen_count < 2:
        return False  # Normal single reopen handling applies

    now_str = helpers.now_str()

    # Escalate to Level 3 (Management) and bump priority by +15
    new_priority = (complaint.get("priority_score", 40)) + 15
    db_conn.complaints.update_one(
        {"_id": c_oid},
        {"$set": {
            "escalation_level": 3,
            "is_chronic_discontent": True,
            "priority_score": new_priority,
            "updated_at": now_str
        }}
    )

    reason = f"Chronic dissatisfaction: Ticket reopened {reopen_count} times by student."

    # Record escalation
    admins = list(db_conn.users.find({"role": "admin"}))
    for admin in admins:
        db_conn.escalations.insert_one({
            "complaint_id": c_oid,
            "from_level": complaint.get("escalation_level", 0),
            "to_level": 3,
            "reason": reason,
            "notified_user_id": admin["_id"],
            "is_automated": True,
            "escalated_at": now_str
        })

        # Urgent notification
        track_url = f"/complaint/{complaint.get('ticket_code')}"
        db_conn.notifications.insert_one({
            "user_id": admin["_id"],
            "message": f"🚨 CHRONIC REOPEN: Ticket {complaint.get('ticket_code')} reopened {reopen_count}x. Dean review required!",
            "link": track_url,
            "is_read": False,
            "created_at": now_str
        })

        # Email Dean / Administrators
        if admin.get("email"):
            mail.send_async(
                admin["email"],
                f"[URGENT - Multi-Reopen] Ticket {complaint.get('ticket_code')} Reopened {reopen_count} Times",
                f"<p>Attention <strong>Institutional Leadership</strong>,</p>"
                f"<p>Ticket <strong>{complaint.get('ticket_code')}</strong> ({complaint.get('subject')}) "
                f"has been reopened <strong>{reopen_count} times</strong> by the student, indicating chronic dissatisfaction.</p>"
                f"<p>The automation engine has escalated this ticket to <strong>Management / Dean Level</strong> with priority score {new_priority}.</p>"
            )

    # Status audit log
    db_conn.complaint_status_history.insert_one({
        "complaint_id": c_oid,
        "old_status": complaint.get("status"),
        "new_status": "Reopened",
        "remark": f"AUTOMATION: Chronic reopen detected ({reopen_count}x). Escalated directly to Principal / Dean level.",
        "changed_by": None,
        "is_automated": True,
        "created_at": now_str
    })

    return True


