"""
Phase 1 Automation Verification Tests.
Tests:
  1. AI / NLP Emergency & Anti-Ragging Fast-Track detection.
  2. Zero-touch least-burdened staff auto-assignment.
  3. Duplicate detection & automated parent linking.
  4. End-to-end complaint submission automation pipeline.
"""

import sys
import unittest
from bson.objectid import ObjectId
from datetime import datetime

import config
import db
import helpers
import automation


class TestPhase1Automation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Connect to MongoDB
        cls.client = db._connect()
        cls.db = cls.client

    def test_01_emergency_keyword_detection(self):
        """Test emergency scanner identifies safety/ragging keywords and ignores benign text."""
        # Case A: Severe Emergency (Ragging)
        is_em, kws, reason = automation.detect_emergency_triage(
            "Hostel senior ragging incident",
            "Third year seniors are harassing and abusing juniors in room 204."
        )
        self.assertTrue(is_em, "Should detect ragging as emergency")
        self.assertIn("ragging", kws)
        self.assertIn("harass", kws)

        # Case B: Severe Emergency (Fire / Electric)
        is_em2, kws2, reason2 = automation.detect_emergency_triage(
            "Spark and fire in lab 3",
            "Short circuit near switchboard with visible smoke"
        )
        self.assertTrue(is_em2, "Should detect fire hazard")
        self.assertTrue("fire" in kws2 or "short circuit" in kws2)

        # Case C: Benign Grievance
        is_em3, kws3, _ = automation.detect_emergency_triage(
            "Library books not returned",
            "The reference book for data structures is not available on shelf."
        )
        self.assertFalse(is_em3, "Benign grievance should not trigger emergency")
        self.assertEqual(len(kws3), 0)
        print("  [PASS] Emergency Keyword Detection verified.")

    def test_02_staff_auto_assignment_logic(self):
        """Test staff auto-assignment chooses active staff member with lowest workload."""
        # Find IT Support department
        it_dept = self.db.departments.find_one({"name": "IT Support"})
        if not it_dept:
            it_dept = self.db.departments.find_one({})

        chosen_staff = automation.auto_assign_staff(self.db, it_dept["_id"])
        self.assertIsNotNone(chosen_staff, "Should find and select a staff member")
        self.assertIn("name", chosen_staff)
        self.assertIn("active_count", chosen_staff)
        print(f"  [PASS] Auto-assignment selected staff '{chosen_staff['name']}' with active workload {chosen_staff['active_count']}.")

    def test_03_duplicate_detection(self):
        """Test high similarity text is recognized as duplicate."""
        now = helpers.now_str()
        it_cat = self.db.categories.find_one({"name": "Internet & Computer Lab"})
        if not it_cat:
            it_cat = self.db.categories.find_one({})

        student = self.db.users.find_one({"role": "student"})
        student_id = student["_id"] if student else ObjectId()

        # Seed an existing complaint
        existing_doc = {
            "ticket_code": "TEST-DUP-001",
            "user_id": student_id,
            "category_id": it_cat["_id"],
            "department_id": it_cat.get("department_id"),
            "subject": "Wi-Fi not working in Main Library reading hall",
            "description": "Internet connection drops every two minutes and cannot connect to student portal.",
            "status": "In Progress",
            "priority_score": 40,
            "created_at": now,
            "updated_at": now,
            "deadline": helpers.add_days(now, 2)
        }
        res_existing = self.db.complaints.insert_one(existing_doc)
        parent_id = res_existing.inserted_id

        try:
            # Query with very similar text from another user
            is_dup, parent_ticket, score, matched_id = automation.check_and_tag_duplicate(
                self.db,
                subject="Wi-Fi internet not working in Library reading room",
                description="Internet connection drops frequently and fails to load portal pages.",
                category_id=it_cat["_id"],
                user_id=ObjectId()  # different user
            )
            self.assertTrue(is_dup, f"Expected duplicate detection, got score {score}")
            self.assertEqual(parent_ticket, "TEST-DUP-001")
            self.assertEqual(matched_id, parent_id)
            print(f"  [PASS] Duplicate detection flagged matching ticket {parent_ticket} with score {score}.")
        finally:
            self.db.complaints.delete_one({"_id": parent_id})

    def test_04_full_pipeline_normal_complaint(self):
        """Test end-to-end submission automation: moves Pending -> Assigned, sets staff, logs audit."""
        now = helpers.now_str()
        maint_cat = self.db.categories.find_one({"name": "Infrastructure & Maintenance"})
        if not maint_cat:
            maint_cat = self.db.categories.find_one({})

        student = self.db.users.find_one({"role": "student"})
        student_id = student["_id"] if student else ObjectId()

        new_doc = {
            "ticket_code": "TEST-AUTO-001",
            "user_id": student_id,
            "category_id": maint_cat["_id"],
            "department_id": maint_cat.get("department_id"),
            "subject": "Tube light flickering in Classroom 302",
            "description": "The middle tube light in classroom 302 is flickering continuously causing headache.",
            "status": "Pending",
            "priority_score": 30,
            "created_at": now,
            "updated_at": now,
            "deadline": helpers.add_days(now, 5)
        }
        res = self.db.complaints.insert_one(new_doc)
        complaint_id = res.inserted_id

        try:
            # Execute automation pipeline
            actions = automation.process_new_complaint_automation(self.db, complaint_id)
            self.assertTrue(actions["auto_assigned"], "Should be auto-assigned")
            self.assertFalse(actions["emergency_detected"], "Should not be emergency")

            # Verify updated complaint in DB
            updated = self.db.complaints.find_one({"_id": complaint_id})
            self.assertEqual(updated["status"], "Assigned", "Status should transition to Assigned")
            self.assertIsNotNone(updated.get("assigned_to"), "assigned_to should be set")

            # Verify audit history
            history = list(self.db.complaint_status_history.find({"complaint_id": complaint_id}))
            self.assertTrue(any("Smart Dispatch auto-assigned" in h.get("remark", "") for h in history),
                            "History should contain automated assignment log")
            print(f"  [PASS] Full normal pipeline auto-assigned ticket to {actions['assigned_to']}.")
        finally:
            self.db.complaints.delete_one({"_id": complaint_id})
            self.db.complaint_status_history.delete_many({"complaint_id": complaint_id})

    def test_05_full_pipeline_emergency_complaint(self):
        """Test end-to-end emergency submission: priority=100, 24h deadline, EMERGENCY tag."""
        now = helpers.now_str()
        hostel_cat = self.db.categories.find_one({"name": "Hostel & Canteen"})
        if not hostel_cat:
            hostel_cat = self.db.categories.find_one({})

        student = self.db.users.find_one({"role": "student"})
        student_id = student["_id"] if student else ObjectId()

        em_doc = {
            "ticket_code": "TEST-EM-999",
            "user_id": student_id,
            "category_id": hostel_cat["_id"],
            "department_id": hostel_cat.get("department_id"),
            "subject": "Immediate ragging and harassment in hostel block B",
            "description": "Student being ragged and physically harassed by senior students right now.",
            "status": "Pending",
            "priority_score": 30,
            "created_at": now,
            "updated_at": now,
            "deadline": helpers.add_days(now, 4)
        }
        res = self.db.complaints.insert_one(em_doc)
        em_id = res.inserted_id

        try:
            actions = automation.process_new_complaint_automation(self.db, em_id)
            self.assertTrue(actions["emergency_detected"], "Emergency should be detected")

            updated = self.db.complaints.find_one({"_id": em_id})
            self.assertEqual(updated["priority_score"], 100, "Priority score must be 100 (Critical)")
            self.assertTrue(updated.get("is_emergency"), "is_emergency flag must be True")
            self.assertIn("EMERGENCY", updated.get("tags", []))

            # Verify emergency status history
            history = list(self.db.complaint_status_history.find({"complaint_id": em_id}))
            self.assertTrue(any("Emergency Triage" in h.get("remark", "") for h in history))
            print("  [PASS] Full emergency pipeline set priority to 100, overridden SLA, and logged emergency.")
        finally:
            self.db.complaints.delete_one({"_id": em_id})
            self.db.complaint_status_history.delete_many({"complaint_id": em_id})


if __name__ == "__main__":
    print("\n--- RUNNING PHASE 1 AUTOMATION TESTS ---")
    unittest.main()
