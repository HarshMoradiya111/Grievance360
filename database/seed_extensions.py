"""Seed demo data for M9-M13 tables."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config, db, helpers
from datetime import datetime, timedelta

app_cfg = type('C', (), {'SECRET_KEY': config.SECRET_KEY,
                          'UPLOAD_FOLDER': config.UPLOAD_FOLDER,
                          'MAX_CONTENT_LENGTH': config.MAX_CONTENT_LENGTH})

# Get a db connection directly
conn = db._connect()

def q(sql, params=()):
    cur = conn.cursor(); cur.execute(sql, params)
    return cur.fetchall()

def q1(sql, params=()):
    cur = conn.cursor(); cur.execute(sql, params)
    return cur.fetchone()

def ex(sql, params=()):
    cur = conn.cursor(); cur.execute(sql, params)
    conn.commit()
    return cur.lastrowid

now = helpers.now_str()

# ---- IDs ----
admin = q1("SELECT id FROM users WHERE role='admin' LIMIT 1")["id"]
categories = {r["name"]: r["id"] for r in q("SELECT id, name FROM categories")}
complaints  = q("SELECT id, ticket_code, status FROM complaints ORDER BY id")
students    = q("SELECT id FROM users WHERE role='student'")
open_comps  = [c for c in complaints if c["status"] not in ("Resolved","Closed","Rejected")]

# ---- KB articles ----
articles = [
    ("How do I apply for a re-evaluation or revaluation of marks?",
     "To apply for revaluation, fill in the revaluation form available at the Examination office window (Room 101) within 10 days of result declaration. Attach a photocopy of your answer sheet. The fee is ₹150 per subject. Results are typically declared within 45 days.",
     categories.get("Examination & Results")),
    ("What do I do if the college Wi-Fi is not working in my hostel room?",
     "First check that the Wi-Fi password you are using is the current one — it changes every semester and is posted on the notice board outside the IT Support office. If the password is correct, log a complaint through the portal with your room number. The IT team attends to hostel Wi-Fi faults within 24 hours on weekdays.",
     categories.get("Internet & Computer Lab")),
    ("The washroom tap in my block is leaking. Who do I contact?",
     "Log a maintenance complaint through this portal under the Infrastructure & Maintenance category. Please mention the block name and floor number in the description. Maintenance responds within 3 working days. For an emergency (flooding), call the maintenance control room on ext. 2200.",
     categories.get("Infrastructure & Maintenance")),
    ("How do I request a transfer certificate or leaving certificate?",
     "Submit a written application to the Administrative Office with your enrolment number and reason. Attach a clearance form signed by the Library, Hostel (if applicable), and Finance sections. Processing takes 7 working days. You will receive an SMS notification when the certificate is ready.",
     categories.get("Examination & Results")),
    ("The projector in lab 3 is not working. What should I do?",
     "Log a complaint under Internet & Computer Lab with the lab number and the time of the incident. IT Support aims to resolve lab equipment issues the same day when reported before 2 PM.",
     categories.get("Internet & Computer Lab")),
]
for title, body, cat_id in articles:
    ex("INSERT INTO kb_articles (title, body, category_id, is_published, views, "
       "helpful_yes, helpful_no, deflections, author_id, published_at) "
       "VALUES (%s,%s,%s,1,%s,%s,0,0,%s,%s)",
       (title, body, cat_id, 10 + len(title) % 40, 5 + len(title) % 12, admin, now))
print("  %d KB articles" % len(articles))

# ---- Announcements ----
start_past  = (datetime.now() - timedelta(days=2)).strftime(helpers.DT_FORMAT)
end_future  = (datetime.now() + timedelta(days=7)).strftime(helpers.DT_FORMAT)
end_past    = (datetime.now() - timedelta(days=1)).strftime(helpers.DT_FORMAT)
start_soon  = (datetime.now() + timedelta(hours=2)).strftime(helpers.DT_FORMAT)
end_soon    = (datetime.now() + timedelta(days=3)).strftime(helpers.DT_FORMAT)

anns = [
    ("Campus Wi-Fi maintenance — 11 PM to 1 AM tonight",
     "The IT team will be performing scheduled maintenance on the campus Wi-Fi infrastructure tonight between 11 PM and 1 AM. Expect 60–90 minutes of interrupted connectivity. Plan your downloads accordingly.",
     "all", None, categories.get("Internet & Computer Lab"), start_past, end_future, 1),
    ("Exam hall ticket download now open",
     "Hall tickets for the Semester 3 examinations are now available for download from the student portal. The download window closes 48 hours before the first examination. Print two copies and carry the original ID card.",
     "student", None, categories.get("Examination & Results"), start_past, end_future, 1),
    ("Hostel water supply interrupted — 9 AM to 12 PM Saturday",
     "Due to municipal pipeline work, the hostel water supply will be interrupted this Saturday from 9 AM to 12 PM. Overhead tanks will be filled before the cutoff. The kitchen will operate normally.",
     "student", None, None, start_past, end_soon, 1),
    ("End-of-term infrastructure survey",
     "The Maintenance department has opened a short survey to identify recurring infrastructure problems. Please submit your observations through the portal under Infrastructure & Maintenance — your input shapes the next maintenance cycle.",
     "all", None, None, start_past, end_future, 1),
]
for title, body, audience, dept_id, cat_id, starts, ends, is_active in anns:
    ex("INSERT INTO announcements (title, body, audience_role, department_id, "
       "category_id, starts_at, ends_at, is_active, author_id) "
       "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
       (title, body, audience, dept_id, cat_id, starts, ends, is_active, admin))
print("  %d announcements" % len(anns))

# ---- Supporters (M10): a few students endorse some open complaints ----
support_added = 0
for comp in open_comps[:6]:
    for student in students:
        # Don't let the complaint owner endorse their own
        owner = q1("SELECT user_id FROM complaints WHERE id=%s", (comp["id"],))
        if owner and owner["user_id"] == student["id"]: continue
        dup = q1("SELECT id FROM complaint_supporters WHERE complaint_id=%s AND user_id=%s",
                 (comp["id"], student["id"]))
        if not dup:
            ex("INSERT INTO complaint_supporters (complaint_id, user_id, supported_at) "
               "VALUES (%s,%s,%s)", (comp["id"], student["id"], now))
            support_added += 1
        if support_added >= 8: break
    if support_added >= 8: break
print("  %d supporter endorsements" % support_added)

# ---- Escalations (M9): mark a couple of open overdue complaints ----
overdue = [c for c in open_comps if q1(
    "SELECT id FROM complaints WHERE id=%s AND deadline < %s", (c["id"], now))]
esc_added = 0
for comp in overdue[:3]:
    ex("INSERT INTO escalations (complaint_id, from_level, to_level, reason, "
       "notified_user_id, escalated_at) VALUES (%s,0,2,"
       "'Deadline passed — department notified.',%s,%s)",
       (comp["id"], admin, now))
    esc_added += 1
print("  %d escalation records" % esc_added)

conn.close()
print("Extension seed done.")
