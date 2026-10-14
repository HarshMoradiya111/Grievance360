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
from datetime import datetime
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
