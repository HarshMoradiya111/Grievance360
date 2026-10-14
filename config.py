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
# "mongodb"= uses the MongoDB settings below
DB_ENGINE = "mongodb"

# On Vercel the deployed filesystem is read-only; copy the seeded database
# to /tmp (writable) on cold start so the app can write to it.
UPLOAD_FOLDER_DEFAULT = None  # use the project-relative path below

# Used when DB_ENGINE = "mongodb"
MONGO_URI = "mongodb+srv://grievancecharusat_db_user:aAPfZE5SascLlP6x@cluster0.pmbehtz.mongodb.net/?appName=Cluster0"
MONGO_DB = "grievance360"

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
MAIL_ENABLED  = True                        # flip to True once configured
MAIL_SMTP     = "smtp.gmail.com"
MAIL_PORT     = 587                          # TLS
MAIL_USER     = "grievance.charusat@gmail.com"   # your sender address
MAIL_PASSWORD = "sggvrxpfdjvdplmf"                           # app password goes here
MAIL_FROM     = "Grievance360 — CHARUSAT <grievance.charusat@gmail.com>"
PORTAL_URL = "https://grievance360portal.vercel.app"

# -------------------------------------------------------------- automation ---
AUTO_ASSIGN_ENABLED            = True   # Zero-touch smart dispatch to staff
EMERGENCY_TRIAGE_ENABLED       = True   # Fast-track anti-ragging and safety issues
AUTO_DUPLICATE_LINK_ENABLED    = True   # Auto-tag and cluster similar complaints
EMERGENCY_SLA_DAYS             = 1      # 24-hour turnaround for emergency complaints
DUPLICATE_SIMILARITY_THRESHOLD = 0.50   # Jaccard threshold for duplicate grouping
AUTO_ESCALATION_ENABLED        = True   # Background daemon for SLA escalations
AUTO_CLOSE_DAYS                = 5      # Days after resolution before auto-close
SLA_WARNING_PERCENT            = 0.75   # Send pre-breach warning at 75% elapsed
STALLED_TICKET_HOURS           = 48     # Hours of inactivity before staff nudge

