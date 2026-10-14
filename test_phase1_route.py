"""
Smoke test HTTP route /complaint/new with authentication and verify automation triggers.
"""
import unittest
from bson.objectid import ObjectId
import app
import db
import helpers

class TestPhase1Route(unittest.TestCase):
    def setUp(self):
        self.app = app.app
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.db = db._connect()

    def test_http_raise_and_auto_assign(self):
        # Find student and ensure profile is complete
        student = self.db.users.find_one({"role": "student"})
        self.db.users.update_one({"_id": student["_id"]}, {"$set": {
            "phone": "9876543210",
            "enrollment_no": "MSCIT2026001",
            "program": "MSc-IT",
            "student_department": "DEPSTAR",
            "semester": "3"
        }})

        cat = self.db.categories.find_one({"name": "Internet & Computer Lab"})
        if not cat:
            cat = self.db.categories.find_one({})

        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(student["_id"])
            sess["_fresh"] = True

        res = self.client.post("/complaint/new", data={
            "category_id": str(cat["_id"]),
            "subject": "HTTP Automation Test - Lab 5 Router",
            "description": "The lab 5 router has been powered off and network drops continuously.",
            "is_anonymous": "0"
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        # Verify in DB that the newly created complaint was auto-assigned
        created = self.db.complaints.find_one({"subject": "HTTP Automation Test - Lab 5 Router"})
        self.assertIsNotNone(created, "Complaint should be created in DB")
        self.assertEqual(created["status"], "Assigned", "Should be auto-assigned upon submission")
        self.assertIsNotNone(created.get("assigned_to"), "assigned_to must be populated")
        print(f"  [PASS] HTTP Route /complaint/new created ticket {created['ticket_code']} and auto-assigned to {created['assigned_to']}.")

        # Cleanup
        self.db.complaints.delete_one({"_id": created["_id"]})
        self.db.complaint_status_history.delete_many({"complaint_id": created["_id"]})

if __name__ == "__main__":
    unittest.main()
