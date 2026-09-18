"""
Grievance360 - configuration.

Switch the whole app between SQLite and MySQL by changing DB_ENGINE below.
Every SQL query in the project is written with MySQL-style '%s' placeholders,
so no query has to change when you switch.
"""

import os
import shutil

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# ---------------------------------------------------------------- database ---
# "sqlite" = runs instantly, no server needed (default, good for development)
# "mysql"  = uses the MySQL settings below (install MySQL Server first)
DB_ENGINE = "sqlite"

# On Vercel the deployed filesystem is read-only; copy the seeded database
# to /tmp (writable) on cold start so the app can write to it.
IS_VERCEL = bool(os.environ.get("VERCEL"))

if IS_VERCEL:
    _src_db = os.path.join(BASE_DIR, "database", "grievance360.db")
    _tmp_db = "/tmp/grievance360.db"
    if not os.path.exists(_tmp_db) and os.path.exists(_src_db):
        shutil.copy2(_src_db, _tmp_db)
    SQLITE_PATH = _tmp_db
    UPLOAD_FOLDER_DEFAULT = "/tmp/uploads"
else:
    SQLITE_PATH = os.path.join(BASE_DIR, "database", "grievance360.db")
    UPLOAD_FOLDER_DEFAULT = None  # use the project-relative path below

# Used when DB_ENGINE = "mysql"
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DB = "grievance360"

# ------------------------------------------------------------------- flask ---
SECRET_KEY = os.environ.get("SECRET_KEY", "grievance360-dev-secret-key-change-me-in-production")

# ------------------------------------------------------------------ uploads ---
UPLOAD_FOLDER = UPLOAD_FOLDER_DEFAULT or os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "docx"}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB per upload

# ---------------------------------------------------------------- business ---
# Complaint statuses used across the whole app. Order matters for the timeline.
STATUSES = [
    "Pending",
    "Assigned",
    "In Progress",
    "Resolved",
    "Closed",
    "Reopened",
    "Rejected",
]

# Statuses that mean "no longer our problem" (used by the SLA breach check).
CLOSED_STATUSES = ("Resolved", "Closed", "Rejected")

# Bootstrap badge colour for each status, so every page colours them the same.
STATUS_COLORS = {
    "Pending": "secondary",
    "Assigned": "info",
    "In Progress": "primary",
    "Resolved": "success",
    "Closed": "dark",
    "Reopened": "warning",
    "Rejected": "danger",
}

# How many complaints per page on the admin list.
PAGE_SIZE = 20

# ------------------------------------------------------------------- email ---
# Set MAIL_ENABLED = True and fill in your Gmail (or other SMTP) credentials.
# For Gmail: enable 2FA, then create an App Password at
#   https://myaccount.google.com/apppasswords
# Use that 16-char app password here — NOT your normal Gmail password.
MAIL_ENABLED  = False                        # flip to True once configured
MAIL_SMTP     = "smtp.gmail.com"
MAIL_PORT     = 587                          # TLS
MAIL_USER     = "grievance360.charusat@gmail.com"   # your sender address
MAIL_PASSWORD = ""                           # app password goes here
MAIL_FROM     = "Grievance360 — CHARUSAT <grievance360.charusat@gmail.com>"
# On Vercel, VERCEL_URL is injected automatically (no https:// prefix)
PORTAL_URL = (
    "https://" + os.environ["VERCEL_URL"]
    if os.environ.get("VERCEL_URL")
    else "http://127.0.0.1:5000"
)
