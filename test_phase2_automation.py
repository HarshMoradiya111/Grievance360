"""
Phase 2 Automation Verification Tests.
Tests:
  1. Automated Escalation Daemon (replaces manual sweep).
  2. SLA Pre-Breach Early Warning (Yellow Alert at 75% elapsed SLA).
  3. Stalled Ticket Inactivity Nudge (48h without progress).
  4. Consolidated lifecycle sweep runner.
  5. Secure HTTP Cron API endpoint (/api/cron/lifecycle-sweep).
"""

import unittest
from datetime import datetime, timedelta
from bson.objectid import ObjectId

import app
import config
import db
import helpers
import automation


class TestPhase2Automation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = db._connect()
        cls.app = app.app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_01_automated_escalation_daemon(self):
        """Test background escalation daemon advances levels, writes escalation log & notifications."""
        # Create an overdue ticket (elapsed ratio > 1.0)
        now_dt = datetime.now()
        created_at = (now_dt - timedelta(days=10)).strftime(helpers.DT_FORMAT)
        deadline = (now_dt - timedelta(days=2)).strftime(helpers.DT_FORMAT)

        student = self.db.users.find_one({"role": "student"})
        staff = self.db.users.find_one({"role": "staff"})
        dept = self.db.departments.find_one({})
        cat = self.db.categories.find_one({})

        test_doc = {
            "ticket_code": "TEST-ESC-001",
            "user_id": student["_id"],
            "assigned_to": staff["_id"],
            "department_id": dept["_id"],
            "category_id": cat["_id"],
            "subject": "Overdue Campus Repair for Escalation Test",
            "description": "This complaint was created 10 days ago and deadline passed 2 days ago.",
            "status": "Assigned",
            "priority_score": 50,
            "escalation_level": 0,
            "created_at": created_at,
            "updated_at": created_at,
            "deadline": deadline
        }
        res = self.db.complaints.insert_one(test_doc)
        cid = res.inserted_id

        try:
            # Run escalation engine
            esc_res = automation.run_automated_escalations(self.db)
            self.assertGreaterEqual(esc_res.get("escalated", 0), 1, "Should have escalated at least 1 ticket")

            # Check that escalation record exists
            esc_record = self.db.escalations.find_one({"complaint_id": cid})
            self.assertIsNotNone(esc_record, "Escalation record should be created")
            self.assertGreaterEqual(esc_record["to_level"], 2, "Should be at least Department (Level 2) or Management (Level 3)")

            # Check complaint document updated
            updated_c = self.db.complaints.find_one({"_id": cid})
            self.assertGreaterEqual(updated_c.get("escalation_level", 0), 2)

            # Check audit history
            history = list(self.db.complaint_status_history.find({"complaint_id": cid}))
            self.assertTrue(any("AUTOMATION DAEMON: Ticket auto-escalated" in h.get("remark", "") for h in history))
            print(f"  [PASS] Automated Escalation Daemon escalated ticket {test_doc['ticket_code']} to Level {esc_record['to_level']}.")
        finally:
            self.db.complaints.delete_one({"_id": cid})
            self.db.escalations.delete_many({"complaint_id": cid})
            self.db.complaint_status_history.delete_many({"complaint_id": cid})

    def test_02_sla_pre_breach_warning(self):
        """Test pre-breach early warning fires when ticket hits 75% elapsed SLA."""
        now_dt = datetime.now()
        # Total window = 4 days, elapsed = 3.2 days (80% ratio)
        created_at = (now_dt - timedelta(days=3.2)).strftime(helpers.DT_FORMAT)
        deadline = (now_dt + timedelta(days=0.8)).strftime(helpers.DT_FORMAT)

        student = self.db.users.find_one({"role": "student"})
        staff = self.db.users.find_one({"role": "staff"})
        dept = self.db.departments.find_one({})
        cat = self.db.categories.find_one({})

        test_doc = {
            "ticket_code": "TEST-WARN-075",
            "user_id": student["_id"],
            "assigned_to": staff["_id"],
            "department_id": dept["_id"],
            "category_id": cat["_id"],
            "subject": "Approaching SLA Deadline",
            "description": "This ticket has used 80% of allowed time and needs early warning.",
            "status": "In Progress",
            "priority_score": 40,
            "created_at": created_at,
            "updated_at": created_at,
            "deadline": deadline,
            "pre_breach_warned": False
        }
        res = self.db.complaints.insert_one(test_doc)
        cid = res.inserted_id

        try:
            warn_res = automation.check_sla_pre_breach_warnings(self.db)
            self.assertGreaterEqual(warn_res.get("pre_breach_warned", 0), 1)

            # Check DB updated
            updated_c = self.db.complaints.find_one({"_id": cid})
            self.assertTrue(updated_c.get("pre_breach_warned"))

            # Check in-app notification
            notif = self.db.notifications.find_one({
                "user_id": staff["_id"],
                "message": {"$regex": "SLA Early Warning"}
            })
            self.assertIsNotNone(notif, "Staff should receive SLA early warning notification")
            print(f"  [PASS] SLA Pre-Breach Early Warning sent for {test_doc['ticket_code']}.")
        finally:
            self.db.complaints.delete_one({"_id": cid})
            self.db.complaint_status_history.delete_many({"complaint_id": cid})

    def test_03_stalled_ticket_nudge(self):
        """Test stalled ticket nudge detects 48+ hours of inactivity."""
        now_dt = datetime.now()
        # 60 hours ago
        stalled_time = (now_dt - timedelta(hours=60)).strftime(helpers.DT_FORMAT)

        student = self.db.users.find_one({"role": "student"})
        staff = self.db.users.find_one({"role": "staff"})
        dept = self.db.departments.find_one({})
        cat = self.db.categories.find_one({})

        test_doc = {
            "ticket_code": "TEST-STALL-048",
            "user_id": student["_id"],
            "assigned_to": staff["_id"],
            "department_id": dept["_id"],
            "category_id": cat["_id"],
            "subject": "Stalled Ticket Without Staff Updates",
            "description": "Staff has not touched this ticket for over 48 hours.",
            "status": "In Progress",
            "priority_score": 35,
            "created_at": stalled_time,
            "updated_at": stalled_time,
            "deadline": (now_dt + timedelta(days=5)).strftime(helpers.DT_FORMAT)
        }
        res = self.db.complaints.insert_one(test_doc)
        cid = res.inserted_id

        try:
            nudge_res = automation.check_stalled_complaints(self.db)
            self.assertGreaterEqual(nudge_res.get("nudged", 0), 1)

            # Check DB updated with last_stalled_nudge_at
            updated_c = self.db.complaints.find_one({"_id": cid})
            self.assertIsNotNone(updated_c.get("last_stalled_nudge_at"))

            # Check staff notification
            notif = self.db.notifications.find_one({
                "user_id": staff["_id"],
                "message": {"$regex": "Inactivity Nudge"}
            })
            self.assertIsNotNone(notif, "Staff should receive inactivity nudge")
            print(f"  [PASS] Stalled ticket nudge sent for {test_doc['ticket_code']}.")
        finally:
            self.db.complaints.delete_one({"_id": cid})
            self.db.complaint_status_history.delete_many({"complaint_id": cid})

    def test_04_consolidated_lifecycle_sweep(self):
        """Test run_lifecycle_sweep executes cleanly and returns structured summary."""
        summary = automation.run_lifecycle_sweep(self.db)
        self.assertIn("timestamp", summary)
        self.assertIn("escalations", summary)
        self.assertIn("sla_warnings", summary)
        self.assertIn("stalled_nudges", summary)
        print("  [PASS] Consolidated lifecycle sweep executed:", summary)

    def test_05_cron_api_endpoint(self):
        """Test /api/cron/lifecycle-sweep endpoint authorization and execution."""
        # 1. Without secret -> 401
        res_unauth = self.client.get("/api/cron/lifecycle-sweep")
        self.assertEqual(res_unauth.status_code, 401)

        # 2. With valid secret -> 200
        res_auth = self.client.get("/api/cron/lifecycle-sweep?secret=grievance360-cron-secret-key")
        self.assertEqual(res_auth.status_code, 200)
        data = res_auth.get_json()
        self.assertTrue(data.get("ok"))
        self.assertIn("result", data)
        print("  [PASS] Secure cron API endpoint verified.")


if __name__ == "__main__":
    print("\n--- RUNNING PHASE 2 AUTOMATION TESTS ---")
    unittest.main()
