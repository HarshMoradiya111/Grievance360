"""
Phase 3 Automation Verification Tests.
Tests:
  1. Grace Period Auto-Closure of Resolved Complaints (5-day grace period).
  2. Post-Resolution CSAT / Feedback Survey Trigger.
  3. Multi-Reopen Direct Escalation to Dean / Management (Chronic dissatisfaction).
  4. End-to-end status update & reopen route integration.
"""

import unittest
from datetime import datetime, timedelta
from bson.objectid import ObjectId

import app
import config
import db
import helpers
import automation


class TestPhase3Automation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = db._connect()
        cls.app = app.app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_01_auto_close_resolved_complaints(self):
        """Test complaints resolved > 5 days ago automatically transition to Closed."""
        now_dt = datetime.now()
        # Resolved 7 days ago
        resolved_at = (now_dt - timedelta(days=7)).strftime(helpers.DT_FORMAT)
        created_at = (now_dt - timedelta(days=12)).strftime(helpers.DT_FORMAT)

        student = self.db.users.find_one({"role": "student"})
        staff = self.db.users.find_one({"role": "staff"})
        dept = self.db.departments.find_one({})
        cat = self.db.categories.find_one({})

        test_doc = {
            "ticket_code": "TEST-AC-005",
            "user_id": student["_id"],
            "assigned_to": staff["_id"],
            "department_id": dept["_id"],
            "category_id": cat["_id"],
            "subject": "Resolved Projector Replacement",
            "description": "Projector was replaced and resolved 7 days ago.",
            "status": "Resolved",
            "priority_score": 25,
            "created_at": created_at,
            "updated_at": resolved_at,
            "resolved_at": resolved_at,
            "deadline": (now_dt - timedelta(days=2)).strftime(helpers.DT_FORMAT)
        }
        res = self.db.complaints.insert_one(test_doc)
        cid = res.inserted_id

        try:
            close_res = automation.auto_close_resolved_complaints(self.db)
            self.assertGreaterEqual(close_res.get("auto_closed", 0), 1)

            # Check DB status is now Closed
            updated_c = self.db.complaints.find_one({"_id": cid})
            self.assertEqual(updated_c["status"], "Closed", "Status must be Closed")
            self.assertIsNotNone(updated_c.get("auto_closed_at"))

            # Check audit history
            history = list(self.db.complaint_status_history.find({"complaint_id": cid}))
            self.assertTrue(any("resolution grace period" in h.get("remark", "") for h in history))

            # Check student notification
            notif = self.db.notifications.find_one({
                "user_id": student["_id"],
                "message": {"$regex": "closed after the 5-day resolution"}
            })
            self.assertIsNotNone(notif)
            print(f"  [PASS] Auto-closure closed resolved ticket {test_doc['ticket_code']}.")
        finally:
            self.db.complaints.delete_one({"_id": cid})
            self.db.complaint_status_history.delete_many({"complaint_id": cid})

    def test_02_post_resolution_feedback_trigger(self):
        """Test marking a complaint Resolved triggers immediate CSAT feedback prompt."""
        now = helpers.now_str()
        student = self.db.users.find_one({"role": "student"})
        staff = self.db.users.find_one({"role": "staff"})
        dept = self.db.departments.find_one({})
        cat = self.db.categories.find_one({})

        test_doc = {
            "ticket_code": "TEST-CSAT-100",
            "user_id": student["_id"],
            "assigned_to": staff["_id"],
            "department_id": dept["_id"],
            "category_id": cat["_id"],
            "subject": "Lab PC Motherboard Repair",
            "description": "Repaired motherboard in Lab 2.",
            "status": "Resolved",
            "priority_score": 30,
            "created_at": now,
            "updated_at": now,
            "resolved_at": now,
            "deadline": helpers.add_days(now, 3)
        }
        res = self.db.complaints.insert_one(test_doc)
        cid = res.inserted_id

        try:
            triggered = automation.trigger_post_resolution_feedback(self.db, cid)
            self.assertTrue(triggered)

            updated_c = self.db.complaints.find_one({"_id": cid})
            self.assertTrue(updated_c.get("feedback_requested"))

            # Check student notification
            notif = self.db.notifications.find_one({
                "user_id": student["_id"],
                "message": {"$regex": "Please rate your experience"}
            })
            self.assertIsNotNone(notif, "Student must receive rating notification")
            print(f"  [PASS] Post-resolution CSAT survey prompt dispatched for {test_doc['ticket_code']}.")
        finally:
            self.db.complaints.delete_one({"_id": cid})
            self.db.complaint_status_history.delete_many({"complaint_id": cid})

    def test_03_multi_reopen_escalation(self):
        """Test reopening 2+ times automatically triggers Dean/Management escalation."""
        now = helpers.now_str()
        student = self.db.users.find_one({"role": "student"})
        staff = self.db.users.find_one({"role": "staff"})
        dept = self.db.departments.find_one({})
        cat = self.db.categories.find_one({})

        test_doc = {
            "ticket_code": "TEST-REOPEN-2X",
            "user_id": student["_id"],
            "assigned_to": staff["_id"],
            "department_id": dept["_id"],
            "category_id": cat["_id"],
            "subject": "Recurring Water Supply Issue in Hostel C",
            "description": "Water tap still leaking despite staff marking resolved twice.",
            "status": "Reopened",
            "reopen_count": 2,
            "priority_score": 40,
            "escalation_level": 0,
            "created_at": now,
            "updated_at": now,
            "deadline": helpers.add_days(now, 3)
        }
        res = self.db.complaints.insert_one(test_doc)
        cid = res.inserted_id

        try:
            escalated = automation.handle_multi_reopen_escalation(self.db, cid, student["_id"])
            self.assertTrue(escalated)

            updated_c = self.db.complaints.find_one({"_id": cid})
            self.assertEqual(updated_c.get("escalation_level"), 3, "Must be escalated to Level 3")
            self.assertTrue(updated_c.get("is_chronic_discontent"))
            self.assertGreater(updated_c.get("priority_score"), 40)

            # Check admin alert notification
            admin = self.db.users.find_one({"role": "admin"})
            notif = self.db.notifications.find_one({
                "user_id": admin["_id"],
                "message": {"$regex": "CHRONIC REOPEN"}
            })
            self.assertIsNotNone(notif, "Admin/Dean should receive chronic reopen alert")
            print(f"  [PASS] Multi-reopen escalated ticket {test_doc['ticket_code']} to Level 3 (Dean Level).")
        finally:
            self.db.complaints.delete_one({"_id": cid})
            self.db.escalations.delete_many({"complaint_id": cid})
            self.db.complaint_status_history.delete_many({"complaint_id": cid})


if __name__ == "__main__":
    print("\n--- RUNNING PHASE 3 AUTOMATION TESTS ---")
    unittest.main()
