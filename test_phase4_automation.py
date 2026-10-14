"""
Phase 4 Automation Verification Tests.
Tests:
  1. Campus Outage & Spike Anomaly Detector.
  2. Scheduled Executive Digest Compilation.
  3. Admin Automation Control Center UI & Action Triggers.
"""

import unittest
from datetime import datetime, timedelta
from bson.objectid import ObjectId

import app
import config
import db
import helpers
import automation


class TestPhase4Automation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = db._connect()
        cls.app = app.app
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

    def test_01_outage_spike_anomaly_detector(self):
        """Test 4+ complaints in 2 hours under same category triggers outage alert & notice."""
        now_dt = datetime.now()
        created_time = (now_dt - timedelta(minutes=15)).strftime(helpers.DT_FORMAT)

        student = self.db.users.find_one({"role": "student"})
        dept = self.db.departments.find_one({"name": "IT Support"})
        if not dept:
            dept = self.db.departments.find_one({})

        cat = self.db.categories.find_one({"department_id": dept["_id"]})
        if not cat:
            cat = self.db.categories.find_one({})

        # Insert 4 complaints in same category
        inserted_ids = []
        for i in range(4):
            doc = {
                "ticket_code": f"TEST-OUTAGE-{i+1}",
                "user_id": student["_id"],
                "department_id": dept["_id"],
                "category_id": cat["_id"],
                "subject": f"Campus Wi-Fi Outage in Block {chr(65+i)}",
                "description": "Entire floor Wi-Fi access point is unreachable and student portal fails to load.",
                "status": "Assigned",
                "priority_score": 30,
                "created_at": created_time,
                "updated_at": created_time,
                "deadline": helpers.add_days(created_time, 2)
            }
            res = self.db.complaints.insert_one(doc)
            inserted_ids.append(res.inserted_id)

        try:
            outages = automation.detect_campus_outage_spike(self.db, lookback_hours=2, threshold=4)
            self.assertGreaterEqual(len(outages), 1, "Should detect at least 1 outage spike")
            self.assertEqual(outages[0]["category_id"], str(cat["_id"]))

            # Verify announcement created
            notice = self.db.announcements.find_one({
                "category_id": cat["_id"],
                "is_automated": True
            })
            self.assertIsNotNone(notice, "Automated advisory notice must be created in announcements")
            self.assertIn("Campus Advisory", notice["title"])

            # Verify admin notification
            admin = self.db.users.find_one({"role": "admin"})
            notif = self.db.notifications.find_one({
                "user_id": admin["_id"],
                "message": {"$regex": "OUTAGE SPIKE"}
            })
            self.assertIsNotNone(notif, "Admin should receive outage spike alert")
            print(f"  [PASS] Outage Detector flagged spike ({outages[0]['complaint_count']} tickets) and published notice.")
        finally:
            self.db.complaints.delete_many({"_id": {"$in": inserted_ids}})
            self.db.announcements.delete_many({"category_id": cat["_id"], "is_automated": True})

    def test_02_executive_digest_generation(self):
        """Test executive digest aggregates statistics cleanly without errors."""
        digest = automation.generate_executive_digest(self.db)
        self.assertIn("timestamp", digest)
        self.assertIn("total_complaints", digest)
        self.assertIn("resolution_rate", digest)
        self.assertIn("top_categories", digest)
        self.assertIsInstance(digest["resolution_rate"], float)
        print(f"  [PASS] Executive Digest compiled ({digest['resolution_rate']}% resolution rate, {digest['total_complaints']} total tickets).")

    def test_03_admin_automation_control_center_routes(self):
        """Test /admin/automation web UI, settings form, and manual action triggers."""
        admin = self.db.users.find_one({"role": "admin"})

        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(admin["_id"])
            sess["_fresh"] = True

        # 1. GET Dashboard
        res_page = self.client.get("/admin/automation")
        self.assertEqual(res_page.status_code, 200)
        self.assertIn(b"Automation Command Center", res_page.data)
        self.assertIn(b"Zero-Touch Staff Auto-Assignment", res_page.data)

        # 2. POST Settings update
        res_settings = self.client.post("/admin/automation/settings", data={
            "auto_assign": "1",
            "emergency_triage": "1",
            "duplicate_link": "1",
            "auto_escalation": "1",
            "auto_close_days": "7",
            "sla_warning_pct": "80",
            "stalled_hours": "36"
        }, follow_redirects=True)
        self.assertEqual(res_settings.status_code, 200)
        self.assertEqual(config.AUTO_CLOSE_DAYS, 7)
        self.assertEqual(config.SLA_WARNING_PERCENT, 0.8)
        self.assertEqual(config.STALLED_TICKET_HOURS, 36)

        # Restore default settings
        config.AUTO_CLOSE_DAYS = 5
        config.SLA_WARNING_PERCENT = 0.75
        config.STALLED_TICKET_HOURS = 48

        # 3. POST Trigger Actions
        res_sweep = self.client.post("/admin/automation/trigger/sweep", follow_redirects=True)
        self.assertEqual(res_sweep.status_code, 200)

        res_outage = self.client.post("/admin/automation/trigger/outage", follow_redirects=True)
        self.assertEqual(res_outage.status_code, 200)

        res_digest = self.client.post("/admin/automation/trigger/digest", follow_redirects=True)
        self.assertEqual(res_digest.status_code, 200)

        print("  [PASS] Admin Automation Control Center UI and triggers fully verified.")


if __name__ == "__main__":
    print("\n--- RUNNING PHASE 4 AUTOMATION TESTS ---")
    unittest.main()
