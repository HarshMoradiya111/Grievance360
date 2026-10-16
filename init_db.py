"""
Grievance360 - database initialiser.

Run this once before starting the app:

    python init_db.py

It creates all 8 tables and inserts the seed data (departments, categories and
the login accounts). Passwords are hashed here with Werkzeug rather than being
written into schema.sql, because a hash pasted into a .sql file is a hash
nobody can regenerate.

WARNING: this DROPS and recreates every table. Run it again only when you want
a clean database.
"""

import os
import sys

from werkzeug.security import generate_password_hash

import config
import db
import helpers

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------
DEPARTMENTS = [
    ("Maintenance", "maintenance@college.edu"),
    ("IT Support", "itsupport@college.edu"),
    ("Academics", "academics@college.edu"),
    ("Hostel", "hostel@college.edu"),
]

# (name, department, sla_days, priority_weight)
CATEGORIES = [
    ("Infrastructure & Maintenance", "Maintenance", 5, 3),
    ("Cleanliness & Hygiene", "Maintenance", 3, 2),
    ("Internet & Computer Lab", "IT Support", 2, 4),
    ("Examination & Results", "Academics", 7, 5),
    ("Library & Study Material", "Academics", 10, 1),
    ("Hostel & Canteen", "Hostel", 4, 3),
]

# (name, email, password, role, department, enrollment_no)
USERS = [
    ("System Admin", "admin@grievance360.edu", "admin123", "admin", None, None),

    ("Ramesh Patil", "maintenance.staff@grievance360.edu", "staff123",
     "staff", "Maintenance", None),
    ("Neha Shah", "it.staff@grievance360.edu", "staff123",
     "staff", "IT Support", None),
    ("Dr. Anil Kumar", "academics.staff@grievance360.edu", "staff123",
     "staff", "Academics", None),
    ("Sunita Rao", "hostel.staff@grievance360.edu", "staff123",
     "staff", "Hostel", None),

    ("Harsh Moradiya", "harsh@student.edu", "student123",
     "student", None, "MSCIT2026001"),
    ("Priya Desai", "priya@student.edu", "student123",
     "student", None, "MSCIT2026002"),
    ("Arjun Mehta", "arjun@student.edu", "student123",
     "student", None, "MSCIT2026003"),
]


def run_schema(connection):
    """Execute the schema file that matches the configured engine."""
    if config.DB_ENGINE == "sqlite":
        schema_file = os.path.join(BASE_DIR, "database", "schema_sqlite.sql")
        script = open(schema_file, encoding="utf-8").read()
        # sqlite3 can run a whole multi-statement script in one call.
        connection._connection.executescript(script)
        connection.commit()
    else:
        # For MySQL the database + tables are created by running
        # database/schema.sql through the mysql client first, so here we just
        # clear the tables out in foreign-key-safe order.
        cursor = connection.cursor()
        for table in ("notifications", "feedback", "comments",
                      "complaint_status_history", "complaints",
                      "users", "categories", "departments"):
            cursor.execute("DELETE FROM " + table)
        connection.commit()
        cursor.close()
    print("  tables created")


def seed(connection):
    cursor = connection.cursor()
    stamp = helpers.now_str()

    # -- departments ---------------------------------------------------------
    dept_ids = {}
    for name, email in DEPARTMENTS:
        cursor.execute(
            "INSERT INTO departments (name, email, created_at) "
            "VALUES (%s, %s, %s)",
            (name, email, stamp),
        )
        dept_ids[name] = cursor.lastrowid
    print("  %d departments" % len(DEPARTMENTS))

    # -- categories ----------------------------------------------------------
    for name, dept, sla_days, weight in CATEGORIES:
        cursor.execute(
            "INSERT INTO categories "
            "(name, department_id, sla_days, priority_weight, created_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (name, dept_ids[dept], sla_days, weight, stamp),
        )
    print("  %d categories" % len(CATEGORIES))

    # -- users ---------------------------------------------------------------
    for name, email, password, role, dept, enrollment in USERS:
        cursor.execute(
            "INSERT INTO users "
            "(name, email, password_hash, role, department_id, "
            " enrollment_no, is_active, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, 1, %s)",
            (
                name,
                email,
                generate_password_hash(password),
                role,
                dept_ids.get(dept) if dept else None,
                enrollment,
                stamp,
            ),
        )
    print("  %d users" % len(USERS))

    connection.commit()
    cursor.close()


def main():
    print("Grievance360 database setup (engine: %s)" % config.DB_ENGINE)

    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    if config.DB_ENGINE == "mongodb":
        import seed_mongo
        print("\nDone. Login accounts:")
        print("  admin    %-28s / %s" % ("admin@grievance360.edu", "admin123"))
        print("  staff    %-28s / %s" % ("it.staff@grievance360.edu", "staff123"))
        print("  student  %-28s / %s" % ("harsh@student.edu", "student123"))
        print("Then:  python app.py")
        return

    if config.DB_ENGINE == "sqlite":
        os.makedirs(os.path.dirname(config.SQLITE_PATH), exist_ok=True)

    try:
        connection = db._connect()
    except Exception as error:
        print("\nCould not connect to the database: %s" % error)
        if config.DB_ENGINE == "mysql":
            print("Run 'mysql -u root -p < database/schema.sql' first, and "
                  "check the MYSQL_* settings in config.py.")
        sys.exit(1)

    run_schema(connection)
    seed(connection)
    connection.close()

    print("\nDone. Login accounts:")
    print("  admin    %-28s / %s" % ("admin@grievance360.edu", "admin123"))
    print("  staff    %-28s / %s" % ("it.staff@grievance360.edu", "staff123"))
    print("  student  %-28s / %s" % ("harsh@student.edu", "student123"))
    print("\nNext:  python database/sample_data.py   (optional demo complaints)")
    print("Then:  python app.py")


if __name__ == "__main__":
    main()
