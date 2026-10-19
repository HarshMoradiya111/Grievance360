"""Business logic helpers — pure functions used by the routes."""

import os
import re
import secrets
from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

import config

# Datetime format used for every date we store. Both MySQL DATETIME and SQLite
# TEXT accept and correctly sort this exact layout.
DT_FORMAT = "%Y-%m-%d %H:%M:%S"


# Date helpers in Python (MySQL/SQLite date functions differ)
def now_str():
    """Current time as a storable string."""
    return datetime.now().strftime(DT_FORMAT)


def to_dt(value):
    """Turn a stored value back into a datetime, whichever engine gave it."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value  # MySQL driver already returns datetime objects
    try:
        return datetime.strptime(str(value)[:19], DT_FORMAT)
    except ValueError:
        return None


def add_days(start, days):
    """Return start + days as a storable string."""
    base = to_dt(start) or datetime.now()
    return (base + timedelta(days=int(days))).strftime(DT_FORMAT)


def pretty_date(value):
    """Human-friendly date for templates, e.g. '17 Aug 2026, 03:45 PM'."""
    moment = to_dt(value)
    return moment.strftime("%d %b %Y, %I:%M %p") if moment else "-"


def time_ago(value):
    """Return human-friendly relative time string like 'Just now', '5 mins ago', '5 hours ago', '2 days ago'."""
    moment = to_dt(value)
    if not moment:
        return ""
    diff = datetime.now() - moment
    seconds = int(diff.total_seconds())
    if seconds < 0:
        return "Just now"
    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    weeks = days // 7
    if weeks < 4:
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    return pretty_date(moment)


def days_between(start, end=None):
    """Whole days from start until end (default: now). Never negative."""
    begin = to_dt(start)
    if begin is None:
        return 0
    finish = to_dt(end) if end else datetime.now()
    if finish is None:
        finish = datetime.now()
    return max(0, (finish - begin).days)


# ---------------------------------------------------------------------------
# Ticket codes
# ---------------------------------------------------------------------------
def make_ticket_code(last_id):
    """Return the next ticket code, e.g. GRV-2026-0007."""
    return "GRV-%d-%04d" % (datetime.now().year, int(last_id) + 1)


# Priority: (weight*10) + (age_days*2) + (reopen*5) + (supporters*3)
def priority_score(priority_weight, created_at, reopen_count=0,
                   supporter_count=0):
    """Compute live priority score. Higher = more urgent."""
    weight_part = int(priority_weight or 1) * 10
    age_part = days_between(created_at) * 2
    reopen_part = int(reopen_count or 0) * 5
    support_part = int(supporter_count or 0) * 3
    return weight_part + age_part + reopen_part + support_part


def priority_label(score):
    """Turn a raw score into a word + Bootstrap colour for the badge."""
    if score >= 60:
        return ("Critical", "danger")
    if score >= 40:
        return ("High", "warning")
    if score >= 25:
        return ("Medium", "info")
    return ("Low", "secondary")


# SLA breach: open and now > deadline
def is_breached(complaint):
    if complaint.get("status") in config.CLOSED_STATUSES:
        return False
    deadline = to_dt(complaint.get("deadline"))
    return deadline is not None and datetime.now() > deadline


def days_left(complaint):
    """Days remaining before the deadline. Negative means overdue."""
    deadline = to_dt(complaint.get("deadline"))
    if deadline is None:
        return 0
    return (deadline - datetime.now()).days


# Auto-routing: keyword scorer, not ML — explainable and easy to tune
# Department names must exactly match the values in the departments table.
DEPARTMENT_KEYWORDS = {
    "Campus Infrastructure & Maintenance": [
        "fan", "light", "bulb", "tube", "leak", "leakage", "tap", "water",
        "washroom", "toilet", "bathroom", "broken", "chair", "bench", "desk",
        "door", "window", "ac", "air conditioner", "electric", "wiring",
        "power", "socket", "plumbing", "dirty", "cleaning", "garbage", "dustbin",
        "paint", "ceiling", "floor", "wall", "roof", "construction",
    ],
    "IT Infrastructure & Network Services": [
        "wifi", "wi-fi", "internet", "network", "computer", "pc", "laptop",
        "lab", "printer", "projector", "software", "login", "password",
        "portal", "website", "server", "email", "system", "slow", "monitor",
        "keyboard", "mouse", "depstar", "network", "router", "cable",
    ],
    "Academic Affairs & Examination Cell": [
        "exam", "result", "marks", "grade", "syllabus", "lecture", "class",
        "teacher", "faculty", "professor", "attendance", "timetable",
        "assignment", "practical", "subject", "notes", "library", "book",
        "certificate", "transcript", "admission", "fees", "scholarship",
        "hall ticket", "marksheet", "migration", "degree", "convocation",
    ],
    "Hostel Administration & Student Welfare": [
        "hostel", "room", "mess", "food", "canteen", "warden", "roommate",
        "bed", "mattress", "laundry", "hygiene", "meal", "kitchen", "curfew",
        "ragging", "security", "guard", "parking", "bus", "transport",
        "ration", "allotment", "block", "floor", "warden",
    ],
}


def suggest_department(subject, description, departments):
    """Return the best-matching department id, or None if nothing matches."""
    subject_text = (subject or "").lower()
    body_text = (description or "").lower()

    scores = {}
    for dept_name, keywords in DEPARTMENT_KEYWORDS.items():
        total = 0
        for word in keywords:
            # \b...\b = whole word only, so "ac" doesn't match "academics"
            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, subject_text):
                total += 3
            if re.search(pattern, body_text):
                total += 1
        if total:
            scores[dept_name] = total

    if not scores:
        return None

    best_name = max(scores, key=scores.get)
    for dept in departments:
        if dept.get("name") == best_name:
            return dept.get("id") or str(dept.get("_id"))
    return None


# ---------------------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS
    )


def save_upload(file_storage):
    """Validate and save a file. Returns (filename, error) — one is None."""
    if file_storage is None or not getattr(file_storage, "filename", None):
        return None, None  # no file sent -- that is fine, attachments optional

    if not allowed_file(file_storage.filename):
        allowed = ", ".join(sorted(config.ALLOWED_EXTENSIONS))
        return None, "Only these file types are allowed: %s" % allowed

    safe_name = secure_filename(file_storage.filename)
    unique_name = "%s_%s" % (secrets.token_hex(6), safe_name)

    content_type = getattr(file_storage, "content_type", None) or "application/octet-stream"
    file_bytes = file_storage.read()

    # 1. Store in MongoDB GridFS when using MongoDB (preserves files permanently across Vercel lambdas)
    if config.DB_ENGINE == "mongodb":
        try:
            import gridfs
            import db
            fs = gridfs.GridFS(db.get_db())
            fs.put(file_bytes, filename=unique_name, metadata={"content_type": content_type})
        except Exception:
            pass

    # 2. Write to local UPLOAD_FOLDER or /tmp cache if writable
    import tempfile
    target_dirs = [config.UPLOAD_FOLDER, os.path.join(tempfile.gettempdir(), "grievance360_uploads")]
    for target_dir in target_dirs:
        try:
            os.makedirs(target_dir, exist_ok=True)
            with open(os.path.join(target_dir, unique_name), "wb") as f:
                f.write(file_bytes)
            break
        except (OSError, PermissionError):
            continue

    return unique_name, None


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------
def status_color(status):
    """Bootstrap colour name for a status badge."""
    return config.STATUS_COLORS.get(status, "secondary")


def make_reset_token():
    """A one-time, unguessable password-reset token."""
    return secrets.token_urlsafe(32)


# Escalation: ratio-driven (elapsed / allowed), not fixed days
ESCALATION_LEVELS = [
    (0.0, 0, "Normal", "secondary"),
    (0.5, 1, "Reminder", "info"),
    (1.0, 2, "Department", "warning"),
    (2.0, 3, "Management", "danger"),
]


def elapsed_ratio(complaint):
    """How much of the allowed time has been used. 1.0 means the deadline."""
    start = to_dt(complaint.get("created_at"))
    end = to_dt(complaint.get("deadline"))
    if start is None or end is None:
        return 0.0
    window = (end - start).total_seconds()
    if window <= 0:
        return 2.0            # a zero-length window is already exhausted
    return (datetime.now() - start).total_seconds() / window


def escalation_level(complaint):
    """Return (level, label, colour). Closed complaints stay at level 0."""
    if complaint.get("status") in config.CLOSED_STATUSES:
        return (0, "Normal", "secondary")

    ratio = elapsed_ratio(complaint)
    level, label, colour = 0, "Normal", "secondary"
    for threshold, lvl, name, col in ESCALATION_LEVELS:
        if ratio >= threshold:
            level, label, colour = lvl, name, col
    return (level, label, colour)


# Duplicate detection: Jaccard coefficient (intersection / union of word sets)
STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "had", "her", "was", "one", "our", "out", "day", "get", "has", "him",
    "his", "how", "its", "may", "new", "now", "old", "see", "two", "way",
    "who", "boy", "did", "use", "man", "men", "put", "say", "she", "too",
    "this", "that", "with", "from", "have", "been", "were", "they", "them",
    "will", "would", "there", "their", "what", "when", "which", "about",
    "please", "kindly", "sir", "madam", "very", "also", "some", "into",
    "than", "then", "these", "those", "here", "since", "because", "still",
    "even", "just", "only", "such", "same", "again", "every", "much",
}


def significant_words(text):
    """Strip stop words and short words; return the meaningful word set."""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) >= 4 and w not in STOP_WORDS}


def similarity(subject_a, body_a, subject_b, body_b):
    """Jaccard similarity 0–1. Subject match counts double."""
    set_a = significant_words(subject_a) | significant_words(body_a)
    set_b = significant_words(subject_b) | significant_words(body_b)
    if not set_a or not set_b:
        return 0.0

    overlap = set_a & set_b
    union = set_a | set_b

    # Subject agreement counts double.
    subject_overlap = significant_words(subject_a) & significant_words(subject_b)
    score = (len(overlap) + len(subject_overlap)) / float(len(union))
    return min(1.0, score)


# Offer a candidate only above this score. Chosen so that two complaints
# about the same broken facility match, while two unrelated complaints in
# the same category do not.
SIMILARITY_THRESHOLD = 0.35
