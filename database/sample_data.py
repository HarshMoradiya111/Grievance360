"""
Grievance360 - demo data generator.

Creates ~30 realistic complaints spread across categories, statuses and the
last four months, complete with status history, comments, ratings and
notifications, so the dashboard and charts look full during the viva.

Run AFTER init_db.py:

    python database/sample_data.py

Running it twice simply adds another batch of complaints.
"""

import os
import random
import sys
from datetime import datetime, timedelta

# This file lives in database/, but it imports config/db/helpers from the
# project root, so we put the root on the import path first.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import config      # noqa: E402
import db          # noqa: E402
import helpers     # noqa: E402

random.seed(360)   # same demo data every run, so screenshots stay consistent


# (category name, subject, description)
COMPLAINTS = [
    ("Infrastructure & Maintenance", "Ceiling fan not working in Room 204",
     "The ceiling fan in classroom 204 has been dead for a week. The room "
     "becomes unbearable during afternoon lectures."),
    ("Infrastructure & Maintenance", "Broken bench in the second-year classroom",
     "Two benches in the second-year classroom are broken at the joint and "
     "wobble badly. Someone will get hurt."),
    ("Infrastructure & Maintenance", "Water leakage near the main staircase",
     "There is constant water leakage from the pipe near the main staircase. "
     "The floor stays wet and slippery all day."),
    ("Infrastructure & Maintenance", "Electric socket sparking in computer lab",
     "The socket at the back of computer lab 2 sparks when anything is "
     "plugged in. This is an electrical safety issue."),
    ("Infrastructure & Maintenance", "Classroom door lock is jammed",
     "The door of room 105 does not lock properly, so the projector and "
     "equipment inside are not secure overnight."),

    ("Cleanliness & Hygiene", "Washroom on the second floor is not cleaned",
     "The washroom on the second floor has not been cleaned for several days. "
     "There is no water in the taps either."),
    ("Cleanliness & Hygiene", "Garbage not collected behind the canteen",
     "Garbage bins behind the canteen have been overflowing for days and the "
     "smell reaches the nearby classrooms."),
    ("Cleanliness & Hygiene", "No soap or handwash in the washrooms",
     "None of the washrooms on the ground floor have soap or handwash "
     "available. This is a basic hygiene requirement."),
    ("Cleanliness & Hygiene", "Dustbins missing from all corridors",
     "The dustbins that used to be in the corridors have been removed, so "
     "students are leaving waste on the floor."),

    ("Internet & Computer Lab", "WiFi keeps disconnecting in the library",
     "The WiFi in the library disconnects every few minutes. It is impossible "
     "to download study material or attend an online session."),
    ("Internet & Computer Lab", "Computers in lab 3 are extremely slow",
     "The computers in lab 3 take almost ten minutes to boot and freeze when "
     "running the practical software."),
    ("Internet & Computer Lab", "Printer in the computer lab is out of order",
     "The printer in the computer lab shows a paper jam error permanently and "
     "nobody has looked at it for two weeks."),
    ("Internet & Computer Lab", "Projector in seminar hall shows no signal",
     "The projector in the seminar hall displays 'no signal' from every "
     "laptop. Presentations had to be cancelled."),
    ("Internet & Computer Lab", "Student portal login fails repeatedly",
     "The student portal rejects my password even after resetting it. I "
     "cannot download my hall ticket."),
    ("Internet & Computer Lab", "No internet in the MSc-IT department",
     "The entire MSc-IT department floor has had no internet access since "
     "Monday morning."),

    ("Examination & Results", "Semester 2 result not published yet",
     "The semester 2 results were promised three weeks ago but are still not "
     "published on the portal."),
    ("Examination & Results", "Marks entered incorrectly for practical exam",
     "My practical exam marks show 12 out of 50 although the internal sheet "
     "displayed 42. Please verify the entry."),
    ("Examination & Results", "Exam timetable clashes for two subjects",
     "Two of my elective subject exams are scheduled at the same time on the "
     "same day in the published timetable."),
    ("Examination & Results", "Hall ticket not generated for my enrollment",
     "My hall ticket is not being generated even though all my fees are paid "
     "and attendance is above the requirement."),
    ("Examination & Results", "Revaluation result pending for two months",
     "I applied for revaluation two months ago and there has been no update "
     "or response since then."),

    ("Library & Study Material", "Reference books not available in library",
     "The reference books listed in the syllabus for advanced database "
     "systems are not available in the library at all."),
    ("Library & Study Material", "Library closes earlier than the notice says",
     "The notice board says the library is open till 8 PM but it is closed by "
     "6 PM every day."),
    ("Library & Study Material", "No seating available during exam period",
     "There is no seating available in the reading hall during the exam "
     "period. Students are sitting on the floor."),
    ("Library & Study Material", "Book return not updated in my account",
     "I returned two books last week but my library account still shows them "
     "as issued and is charging a fine."),

    ("Hostel & Canteen", "Food quality in the mess has dropped badly",
     "The food quality in the hostel mess has become very poor over the last "
     "month. Several students have complained of stomach problems."),
    ("Hostel & Canteen", "No hot water in the hostel bathrooms",
     "The water heater in hostel block B has not worked for two weeks. Bathing "
     "in cold water in this weather is causing students to fall ill."),
    ("Hostel & Canteen", "Canteen overcharging compared to the price list",
     "The canteen is charging more than the rates displayed on the official "
     "price list and refuses to give a bill."),
    ("Hostel & Canteen", "Street lights not working on the hostel path",
     "The lights along the path from the hostel to the main gate are all off, "
     "which feels unsafe late in the evening."),
    ("Hostel & Canteen", "Laundry service has stopped without notice",
     "The hostel laundry service stopped operating without any notice and no "
     "alternative has been arranged."),
    ("Hostel & Canteen", "Drinking water cooler is out of order",
     "The water cooler on the hostel ground floor has been out of order for "
     "over ten days."),
]

STAFF_REMARKS = {
    "Assigned": ["Ticket received and assigned to the concerned team.",
                 "Forwarded to the department for inspection."],
    "In Progress": ["Site inspection completed, work is underway.",
                    "Spare parts have been ordered, work starts tomorrow.",
                    "Our team is currently working on this issue."],
    "Resolved": ["Issue has been fixed and verified on site.",
                 "Repair completed. Please confirm if the problem persists.",
                 "Resolved. The replacement was installed this morning."],
    "Rejected": ["This falls outside our department's scope.",
                 "Could not reproduce the reported issue after inspection."],
}

STUDENT_COMMENTS = [
    "Any update on this please?",
    "This is still not fixed. It has been several days now.",
    "Thank you for looking into it.",
    "Adding more detail: the problem is worse in the mornings.",
]

FEEDBACK_REMARKS = {
    5: "Very quick response, thank you!",
    4: "Resolved well, just took a little longer than expected.",
    3: "Fixed eventually, but communication could be better.",
    2: "Took far too long for such a small issue.",
    1: "Marked resolved but the problem is still there.",
}


def pick_outcome():
    """Choose a status, weighted so the demo data looks like real life."""
    roll = random.random()
    if roll < 0.14:
        return "Pending"
    if roll < 0.28:
        return "Assigned"
    if roll < 0.44:
        return "In Progress"
    if roll < 0.78:
        return "Resolved"
    if roll < 0.90:
        return "Closed"
    if roll < 0.96:
        return "Reopened"
    return "Rejected"


def main():
    print("Grievance360 demo data (engine: %s)" % config.DB_ENGINE)
    connection = db._connect()
    cursor = connection.cursor()

    # -- look up the seed rows created by init_db.py -------------------------
    cursor.execute("SELECT id, name, sla_days, priority_weight, department_id "
                   "FROM categories")
    categories = {row["name"]: row for row in cursor.fetchall()}

    cursor.execute("SELECT id, name, department_id FROM users "
                   "WHERE role = 'staff'")
    staff_by_dept = {row["department_id"]: row for row in cursor.fetchall()}

    cursor.execute("SELECT id FROM users WHERE role = 'student' ORDER BY id")
    students = [row["id"] for row in cursor.fetchall()]

    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    admins = [row["id"] for row in cursor.fetchall()]

    if not categories or not students:
        print("No seed data found. Run 'python init_db.py' first.")
        return

    cursor.execute("SELECT COALESCE(MAX(id), 0) AS last FROM complaints")
    next_id = cursor.fetchone()["last"]

    created_count = 0

    for category_name, subject, description in COMPLAINTS:
        category = categories.get(category_name)
        if category is None:
            continue

        next_id += 1
        student_id = random.choice(students)
        staff = staff_by_dept.get(category["department_id"])

        # Spread creation dates over roughly the last four months.
        age_days = random.randint(1, 120)
        created = datetime.now() - timedelta(
            days=age_days, hours=random.randint(0, 20))
        created_str = created.strftime(helpers.DT_FORMAT)
        deadline_str = (created + timedelta(
            days=category["sla_days"])).strftime(helpers.DT_FORMAT)

        final_status = pick_outcome()
        is_anonymous = 1 if random.random() < 0.15 else 0
        reopen_count = 1 if final_status == "Reopened" else 0
        ticket_code = "GRV-%d-%04d" % (created.year, next_id)

        # -- walk the complaint through its lifecycle ------------------------
        # Each step gets a timestamp after the previous one, so the timeline
        # reads correctly instead of every entry sharing one date.
        steps = [(None, "Pending", "Complaint submitted by student.",
                  student_id, created)]
        moment = created

        if final_status != "Pending":
            moment = moment + timedelta(hours=random.randint(2, 30))
            steps.append(("Pending", "Assigned",
                          random.choice(STAFF_REMARKS["Assigned"]),
                          admins[0] if admins else None, moment))

        if final_status in ("In Progress", "Resolved", "Closed", "Reopened"):
            moment = moment + timedelta(hours=random.randint(4, 40))
            steps.append(("Assigned", "In Progress",
                          random.choice(STAFF_REMARKS["In Progress"]),
                          staff["id"] if staff else None, moment))

        if final_status in ("Resolved", "Closed", "Reopened"):
            moment = moment + timedelta(hours=random.randint(6, 72))
            steps.append(("In Progress", "Resolved",
                          random.choice(STAFF_REMARKS["Resolved"]),
                          staff["id"] if staff else None, moment))

        if final_status == "Closed":
            moment = moment + timedelta(hours=random.randint(2, 48))
            steps.append(("Resolved", "Closed",
                          "Closed after student feedback.", student_id, moment))

        if final_status == "Reopened":
            moment = moment + timedelta(hours=random.randint(6, 60))
            steps.append(("Resolved", "Reopened",
                          "The problem came back within a few days.",
                          student_id, moment))

        if final_status == "Rejected":
            moment = moment + timedelta(hours=random.randint(4, 30))
            steps.append(("Assigned", "Rejected",
                          random.choice(STAFF_REMARKS["Rejected"]),
                          staff["id"] if staff else None, moment))

        resolved_at = None
        for _, new_status, _, _, when in steps:
            if new_status in ("Resolved", "Closed"):
                resolved_at = when.strftime(helpers.DT_FORMAT)

        # A reopened complaint gets a fresh deadline from the reopen date.
        if final_status == "Reopened":
            deadline_str = (moment + timedelta(
                days=category["sla_days"])).strftime(helpers.DT_FORMAT)
            resolved_at = None

        assigned_to = staff["id"] if (staff and final_status != "Pending") else None
        department_id = category["department_id"] if final_status != "Pending" else None

        score = helpers.priority_score(
            category["priority_weight"], created_str, reopen_count)

        cursor.execute(
            "INSERT INTO complaints "
            "(ticket_code, user_id, category_id, department_id, assigned_to, "
            " subject, description, attachment, is_anonymous, status, "
            " priority_score, reopen_count, created_at, updated_at, deadline, "
            " resolved_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, "
            "        %s, %s)",
            (ticket_code, student_id, category["id"], department_id, assigned_to,
             subject, description, is_anonymous, final_status, score,
             reopen_count, created_str,
             moment.strftime(helpers.DT_FORMAT), deadline_str, resolved_at),
        )
        complaint_id = cursor.lastrowid

        for old_status, new_status, remark, changed_by, when in steps:
            cursor.execute(
                "INSERT INTO complaint_status_history "
                "(complaint_id, old_status, new_status, remark, changed_by, "
                " created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (complaint_id, old_status, new_status, remark, changed_by,
                 when.strftime(helpers.DT_FORMAT)),
            )

        # -- a conversation on roughly half the tickets ----------------------
        if random.random() < 0.5:
            comment_time = created + timedelta(hours=random.randint(5, 50))
            cursor.execute(
                "INSERT INTO comments (complaint_id, user_id, message, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (complaint_id, student_id, random.choice(STUDENT_COMMENTS),
                 comment_time.strftime(helpers.DT_FORMAT)),
            )
            if staff and random.random() < 0.7:
                reply_time = comment_time + timedelta(hours=random.randint(1, 20))
                cursor.execute(
                    "INSERT INTO comments "
                    "(complaint_id, user_id, message, created_at) "
                    "VALUES (%s, %s, %s, %s)",
                    (complaint_id, staff["id"],
                     "Thanks for reporting. We are on it.",
                     reply_time.strftime(helpers.DT_FORMAT)),
                )

        # -- ratings on closed tickets ---------------------------------------
        if final_status == "Closed":
            rating = random.choice([5, 5, 4, 4, 4, 3, 3, 2])
            cursor.execute(
                "INSERT INTO feedback "
                "(complaint_id, user_id, rating, remark, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (complaint_id, student_id, rating, FEEDBACK_REMARKS[rating],
                 moment.strftime(helpers.DT_FORMAT)),
            )

        # -- a notification for the student on the latest change --------------
        cursor.execute(
            "INSERT INTO notifications "
            "(user_id, complaint_id, message, link, is_read, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (student_id, complaint_id,
             "%s is now %s" % (ticket_code, final_status),
             "/complaint/%s" % ticket_code,
             0 if random.random() < 0.4 else 1,
             moment.strftime(helpers.DT_FORMAT)),
        )

        created_count += 1

    connection.commit()
    cursor.close()
    connection.close()

    print("  %d complaints created with history, comments and ratings" %
          created_count)
    print("\nStart the app with:  python app.py")


if __name__ == "__main__":
    main()
