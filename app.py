"""Grievance360 — Flask app.  Run: python init_db.py  then  python app.py"""

import io
import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, url_for)
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash
from bson.objectid import ObjectId

import config
import db
import helpers
import mail
import automation

# ===========================================================================
# 1. SETUP & AUTHENTICATION PLUMBING
# ===========================================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

try:
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
except (OSError, PermissionError):
    pass

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"


class User(UserMixin):
    """Wraps a users row so flask-login can carry it around the session."""

    def __init__(self, row):
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]
        self.role = row["role"]
        self.department_id = row.get("department_id")
        self.enrollment_no = row.get("enrollment_no")

    def get_id(self):
        return str(self.id)


@login_manager.user_loader
def load_user(user_id):
    try:
        row = db.get_db().users.find_one({"_id": ObjectId(user_id), "is_active": True})
        if row:
            row["id"] = str(row["_id"])  # Map _id to id for UserMixin
            return User(row)
    except Exception:
        pass
    return None


def role_required(*roles):
    """
    Block anyone whose role is not in the allowed list.

    Always stack it UNDER @login_required so an anonymous visitor gets sent to
    the login page instead of a bare 403:

        @app.route("/admin")
        @login_required
        @role_required("admin")
        def admin_dashboard(): ...
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role not in roles:
                flash("You do not have permission to open that page.", "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_globals():
    """Make these available inside every template without passing them each time."""
    now = helpers.now_str()
    return {
        "status_color": helpers.status_color,
        "pretty_date": helpers.pretty_date,
        "time_ago": helpers.time_ago,
        "priority_label": helpers.priority_label,
        "is_breached": helpers.is_breached,
        "days_left": helpers.days_left,
        "ALL_STATUSES": config.STATUSES,
        "current_year": datetime.now().year,
        "now": now,
    }


@app.template_filter("time_ago")
def filter_time_ago(val):
    return helpers.time_ago(val)


# ===========================================================================
# 2. SHARED HELPERS USED BY MANY ROUTES
# ===========================================================================
def log_status(complaint_id, old_status, new_status, remark, changed_by):
    """Write one row into the audit trail. Called on EVERY status change."""
    db_conn = db.get_db()
    db_conn.complaint_status_history.insert_one({
        "complaint_id": complaint_id,
        "old_status": old_status,
        "new_status": new_status,
        "remark": remark,
        "changed_by": changed_by,
        "created_at": helpers.now_str()
    })

def notify(user_id, message, link=None, complaint_id=None, ticket_code=None, status=None):
    """Drop a notification for a user. Safe to call with user_id=None."""
    if not user_id:
        return
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    u_oid = ObjectId(user_id) if isinstance(user_id, str) and ObjectId.is_valid(user_id) else user_id
    c_oid = ObjectId(complaint_id) if isinstance(complaint_id, str) and ObjectId.is_valid(complaint_id) else complaint_id
    db_conn.notifications.insert_one({
        "user_id": u_oid,
        "user_id_str": str(user_id),
        "complaint_id": c_oid,
        "ticket_code": ticket_code,
        "status": status,
        "message": message,
        "link": link,
        "is_read": False,
        "created_at": helpers.now_str()
    })


def get_complaint_or_404(ticket_code=None, complaint_id=None):
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    query = {}
    if ticket_code:
        query['ticket_code'] = ticket_code
    elif complaint_id:
        query['_id'] = ObjectId(complaint_id) if isinstance(complaint_id, str) else complaint_id

    # We need to lookup category, department, user, assigned_to
    cursor = db_conn.complaints.aggregate([
        {'$match': query},
        {'$lookup': {'from': 'categories', 'localField': 'category_id', 'foreignField': '_id', 'as': 'cat'}},
        {'$lookup': {'from': 'departments', 'localField': 'department_id', 'foreignField': '_id', 'as': 'dept'}},
        {'$lookup': {'from': 'users', 'localField': 'user_id', 'foreignField': '_id', 'as': 'student'}},
        {'$lookup': {'from': 'users', 'localField': 'assigned_to', 'foreignField': '_id', 'as': 'assigned'}}
    ])
    try:
        c = next(cursor)
    except StopIteration:
        abort(404)
        
    c['id'] = str(c['_id'])
    cat = c.get('cat', [{}])[0] if c.get('cat') else {}
    dept = c.get('dept', [{}])[0] if c.get('dept') else {}
    student = c.get('student', [{}])[0] if c.get('student') else {}
    assigned = c.get('assigned', [{}])[0] if c.get('assigned') else {}
    
    c['category_name'] = cat.get('name')
    c['priority_weight'] = cat.get('priority_weight')
    c['sla_days'] = cat.get('sla_days')
    c['department_name'] = dept.get('name')
    c['student_name'] = student.get('name')
    c['student_email'] = student.get('email')
    c['assigned_name'] = assigned.get('name')
    return c


def can_view(complaint):
    """
    Who is allowed to open a complaint?
      admin   -> everything
      staff   -> only what is assigned to them or routed to their department
      student -> only their own
    """
    if getattr(current_user, "role", "") == "admin":
        return True
    if getattr(current_user, "role", "") == "staff":
        return (str(complaint.get("assigned_to")) == str(current_user.id)
                or (complaint.get("department_id") and str(complaint.get("department_id")) == str(getattr(current_user, "department_id", ""))))
    return str(complaint.get("user_id")) == str(current_user.id)


def refresh_priority(complaint):
    """Recompute the live priority score and write it back."""
    db_conn = db.get_db()
    cid = complaint.get("_id") or (ObjectId(complaint["id"]) if isinstance(complaint.get("id"), str) else complaint.get("id"))
    score = helpers.priority_score(
        complaint.get("priority_weight", 1),
        complaint.get("created_at"),
        complaint.get("reopen_count", 0),
        complaint.get("supporter_count", 0),
    )
    if cid:
        db_conn.complaints.update_one({"_id": cid}, {"$set": {"priority_score": score}})
    return score


# Fields every student must fill before raising a complaint.
PROFILE_REQUIRED_FIELDS = [
    ("phone",              "Mobile number"),
    ("enrollment_no",      "Enrollment number"),
    ("program",            "Programme"),
    ("student_department", "Institute / Department"),
    ("semester",           "Current semester"),
]


def student_profile_missing(user_id):
    """Return a list of (field, label) tuples that are still blank.
    Returns an empty list when the profile is complete."""
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    row = db_conn.users.find_one({"_id": ObjectId(user_id)})
    if not row:
        return PROFILE_REQUIRED_FIELDS[:]
    return [(f, lbl) for f, lbl in PROFILE_REQUIRED_FIELDS
            if not (row.get(f) or "").strip()]


# ===========================================================================
# 3. PUBLIC ROUTES
# ===========================================================================
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("home_for_role"))

    try:
        db_conn = db.get_db()
        stats = {
            "total": db_conn.complaints.count_documents({}),
            "resolved": db_conn.complaints.count_documents({"status": {"$in": ["Resolved", "Closed"]}}),
            "categories": db_conn.categories.count_documents({}),
            "departments": db_conn.departments.count_documents({}),
        }
    except Exception as exc:
        app.logger.error("Failed to query stats for index page: %s", exc, exc_info=True)
        stats = {
            "total": 0,
            "resolved": 0,
            "categories": 0,
            "departments": 0,
        }
    return render_template("index.html", stats=stats)


@app.route("/home")
@login_required
def home_for_role():
    """Single place that decides where each role lands after logging in."""
    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))
    if current_user.role == "staff":
        return redirect(url_for("staff_dashboard"))
    return redirect(url_for("student_dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home_for_role"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        enrollment = request.form.get("enrollment_no", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        errors = []
        if len(name) < 3:
            errors.append("Please enter your full name.")
        if "@" not in email or "." not in email:
            errors.append("Please enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("The two passwords do not match.")
        db_conn = db.get_db()
        if db_conn.users.find_one({"email": email}):
            errors.append("That email is already registered. Try logging in.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("register.html", form=request.form)

        db_conn.users.insert_one({
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": "student",
            "enrollment_no": enrollment,
            "phone": phone,
            "is_active": True,
            "created_at": datetime.now()
        })
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home_for_role"))

    if request.method == "POST":
        login_input = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        db_conn = db.get_db()
        # Accept email, username ('admin'), or enrollment number
        query_conditions = [{"email": login_input.lower()}]
        if login_input.lower() == "admin":
            query_conditions.append({"role": "admin"})
            query_conditions.append({"email": "admin@grievance360.edu"})
        else:
            query_conditions.append({"enrollment_no": login_input})
            query_conditions.append({"enrollment_no": login_input.upper()})

        row = db_conn.users.find_one({"$or": query_conditions})
        if row and check_password_hash(row["password_hash"], password):
            if not row.get("is_active"):
                flash("This account has been deactivated.", "danger")
                return render_template("login.html", email=login_input)
            row["id"] = str(row["_id"])
            login_user(User(row))
            flash("Welcome back, %s." % row["name"].split(" ")[0], "success")
            return redirect(url_for("home_for_role"))

        # Deliberately vague: never reveal whether the account exists.
        flash("Incorrect email, username, or password.", "danger")
        return render_template("login.html", email=login_input)

    return render_template("login.html", email="")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Password reset
# Sends an email via SMTP/Resend AND displays the link on screen so users
# in environments without direct mail server access can always reset their password.
# ---------------------------------------------------------------------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    reset_link = None

    if request.method == "POST":
        login_input = request.form.get("email", "").strip()
        db_conn = db.get_db()

        query_conditions = [{"email": login_input.lower()}]
        if login_input.lower() == "admin":
            query_conditions.append({"role": "admin"})
            query_conditions.append({"email": "admin@grievance360.edu"})
        else:
            query_conditions.append({"enrollment_no": login_input})
            query_conditions.append({"enrollment_no": login_input.upper()})

        row = db_conn.users.find_one({"$or": query_conditions})

        if row:
            target_email = row.get("email")
            token = helpers.make_reset_token()
            expires = (datetime.now() + timedelta(hours=1)).strftime(
                helpers.DT_FORMAT)
            db_conn.users.update_one(
                {"_id": row["_id"]},
                {"$set": {"reset_token": token, "reset_expires": expires}}
            )
            reset_path = url_for("reset_password", token=token)
            reset_link = config.PORTAL_URL.rstrip("/") + reset_path
            try:
                mail.notify_password_reset(target_email, reset_link)
            except Exception as exc:
                app.logger.warning("Could not dispatch password reset email to %s: %s", target_email, exc)

        flash("If that account is registered, a password reset link has been sent to your email and generated below.",
              "info")
        return render_template("forgot.html", reset_link=reset_link)

    return render_template("forgot.html", reset_link=None)


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    db_conn = db.get_db()
    row = db_conn.users.find_one({"reset_token": token})

    expired = True
    if row:
        expires = helpers.to_dt(row["reset_expires"])
        expired = expires is None or datetime.now() > expires

    if not row or expired:
        flash("That reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif password != confirm:
            flash("The two passwords do not match.", "danger")
        else:
            db_conn = db.get_db()
            db_conn.users.update_one(
                {"_id": row["_id"]},
                {"$set": {"password_hash": generate_password_hash(password)},
                 "$unset": {"reset_token": "", "reset_expires": ""}}
            )
            flash("Password updated. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("reset.html", token=token)


# ===========================================================================
# 4. STUDENT ROUTES
# ===========================================================================
@app.route("/student")
@login_required
@role_required("student")
def student_dashboard():
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    cursor = db_conn.complaints.aggregate([
        {"$match": {"user_id": ObjectId(current_user.id)}},
        {"$lookup": {
            "from": "categories",
            "localField": "category_id",
            "foreignField": "_id",
            "as": "category"
        }},
        {"$lookup": {
            "from": "departments",
            "localField": "department_id",
            "foreignField": "_id",
            "as": "department"
        }},
        {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
        {"$unwind": {"path": "$department", "preserveNullAndEmptyArrays": True}},
        {"$sort": {"created_at": -1}}
    ])
    complaints = []
    for c in cursor:
        c["id"] = str(c["_id"])
        c["category_name"] = c.get("category", {}).get("name")
        c["department_name"] = c.get("department", {}).get("name")
        complaints.append(c)

    counts = {"total": len(complaints), "open": 0, "resolved": 0, "breached": 0}
    for item in complaints:
        if item["status"] in config.CLOSED_STATUSES:
            counts["resolved"] += 1
        else:
            counts["open"] += 1
        if helpers.is_breached(item):
            counts["breached"] += 1

    profile_missing = student_profile_missing(current_user.id)
    now = helpers.now_str()
    notices_cursor = db_conn.announcements.aggregate([
        {"$match": {
            "is_active": {"$in": [1, True, "1"]},
            "starts_at": {"$lte": now},
            "ends_at": {"$gte": now},
            "audience_role": {"$in": ["all", "student"]}
        }},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$sort": {"starts_at": -1}},
        {"$limit": 3}
    ])
    active_notices = []
    for n in notices_cursor:
        n["id"] = str(n["_id"])
        c = n.get("cat", [{}])[0] if n.get("cat") else {}
        n["category_name"] = c.get("name")
        active_notices.append(n)

    return render_template("student/dashboard.html",
                           complaints=complaints, counts=counts,
                           profile_missing=profile_missing,
                           active_notices=active_notices)


@app.route("/complaint/new", methods=["GET", "POST"])
@login_required
@role_required("student")
def raise_complaint():
    # Profile must be complete before a student can raise a complaint.
    missing = student_profile_missing(current_user.id)
    if missing:
        labels = ", ".join(lbl for _, lbl in missing)
        flash(
            "Please complete your profile before raising a complaint. "
            "Missing: " + labels + ".",
            "warning",
        )
        return redirect(url_for("profile"))

    db_conn = db.get_db()
    categories = list(db_conn.categories.find({}, {"name": 1, "sla_days": 1, "priority_weight": 1}).sort("name", 1))
    # Make sure to stringify IDs for templates
    for cat in categories:
        cat["id"] = str(cat["_id"])

    if request.method == "POST":
        category_id = request.form.get("category_id", "")
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        is_anonymous = 1 if request.form.get("is_anonymous") else 0

        from bson.objectid import ObjectId
        category = db_conn.categories.find_one({"_id": ObjectId(category_id)}) if category_id else None

        errors = []
        if category is None:
            errors.append("Please choose a category.")
        if len(subject) < 5:
            errors.append("Subject must be at least 5 characters.")
        if len(description) < 15:
            errors.append("Please describe the problem in at least 15 characters.")

        attachment, upload_error = helpers.save_upload(request.files.get("attachment"))
        if upload_error:
            errors.append(upload_error)

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("student/raise.html",
                                   categories=categories, form=request.form)

        created_at = helpers.now_str()
        deadline = helpers.add_days(created_at, category.get("sla_days", 5))

        # Insert complaint into MongoDB
        complaint_doc = {
            "ticket_code": "PENDING",
            "user_id": ObjectId(current_user.id),
            "category_id": category["_id"],
            "department_id": category.get("department_id"),
            "subject": subject,
            "description": description,
            "attachment": attachment,
            "is_anonymous": is_anonymous,
            "status": "Pending",
            "priority_score": helpers.priority_score(category.get("priority_weight", 1), created_at, 0),
            "reopen_count": 0,
            "created_at": created_at,
            "updated_at": created_at,
            "deadline": deadline
        }
        res = db_conn.complaints.insert_one(complaint_doc)
        complaint_id = str(res.inserted_id)

        # In MongoDB, we don't have a reliable auto-increment integer ID to make the ticket code.
        # We can use the last 6 chars of the ObjectID.
        ticket_code = helpers.make_ticket_code(int(complaint_id[-6:], 16))
        db_conn.complaints.update_one({"_id": res.inserted_id}, {"$set": {"ticket_code": ticket_code}})

        # log_status is still tied to SQL in app.py unless migrated, but we will migrate it locally here or leave it.
        # Wait, if log_status uses SQL, it will CRASH. So I must inline the MongoDB insert for status history.
        db_conn.complaint_status_history.insert_one({
            "complaint_id": res.inserted_id,
            "old_status": None,
            "new_status": "Pending",
            "remark": "Complaint submitted by student.",
            "changed_by": ObjectId(current_user.id),
            "created_at": created_at
        })

        # Phase 1: Automation Engine Execution (Emergency triage, duplicate detection, auto-assignment)
        try:
            auto_res = automation.process_new_complaint_automation(db_conn, res.inserted_id)
        except Exception as auto_exc:
            auto_res = {"error": str(auto_exc)}

        # Tell every admin a new complaint landed.
        admins = db_conn.users.find({"role": "admin"})
        for admin in admins:
            # Inline notify to MongoDB
            db_conn.notifications.insert_one({
                "user_id": admin["_id"],
                "message": "New complaint %s: %s" % (ticket_code, subject[:50]),
                "link": url_for("track_complaint", ticket_code=ticket_code),
                "is_read": False,
                "created_at": helpers.now_str()
            })

        # Email confirmation to student
        student_row = db_conn.users.find_one({"_id": ObjectId(current_user.id)})
        mail.notify_complaint_submitted(
            student_email=student_row.get("email"),
            student_name=student_row["name"],
            ticket_code=ticket_code,
            subject=subject,
            category=category["name"],
            deadline=helpers.pretty_date(deadline),
        )

        if auto_res.get("emergency_detected"):
            flash("🚨 Emergency Fast-Track: Your complaint has been marked CRITICAL and escalated directly to Campus Security & Dean.", "danger")
        elif auto_res.get("auto_assigned"):
            flash("Complaint %s submitted and automatically assigned to %s." % (ticket_code, auto_res.get("assigned_to")), "success")
        else:
            flash("Complaint submitted. Your ticket number is %s." % ticket_code, "success")

        return redirect(url_for("track_complaint", ticket_code=ticket_code))

    return render_template("student/raise.html", categories=categories, form={})


@app.route("/complaint/<ticket_code>")
@login_required
def track_complaint(ticket_code):
    complaint = get_complaint_or_404(ticket_code=ticket_code)
    if not can_view(complaint):
        flash("You are not allowed to view that complaint.", "danger")
        return redirect(url_for("home_for_role"))

    from bson.objectid import ObjectId
    db_conn = db.get_db()
    
    # History
    history_cursor = db_conn.complaint_status_history.aggregate([
        {"$match": {"complaint_id": ObjectId(complaint["id"])}},
        {"$lookup": {"from": "users", "localField": "changed_by", "foreignField": "_id", "as": "u"}},
        {"$sort": {"created_at": 1, "_id": 1}}
    ])
    history = []
    for h in history_cursor:
        u = h.get("u", [{}])[0] if h.get("u") else {}
        h["changed_by_name"] = u.get("name")
        history.append(h)
        
    # Comments
    comments_cursor = db_conn.comments.aggregate([
        {"$match": {"complaint_id": ObjectId(complaint["id"])}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "u"}},
        {"$sort": {"created_at": 1}}
    ])
    comments = []
    for cm in comments_cursor:
        u = cm.get("u", [{}])[0] if cm.get("u") else {}
        cm["author_name"] = u.get("name")
        cm["author_role"] = u.get("role")
        comments.append(cm)
        
    rating = db_conn.feedback.find_one({"complaint_id": ObjectId(complaint["id"])})

    return render_template("student/track.html", complaint=complaint,
                           history=history, comments=comments, rating=rating)


@app.route("/complaint/<complaint_id>/comment", methods=["POST"])
@login_required
def add_comment(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    if not can_view(complaint):
        abort(403)

    message = request.form.get("message", "").strip()
    if not message:
        flash("Comment cannot be empty.", "warning")
    else:
        from bson.objectid import ObjectId
        db_conn = db.get_db()
        db_conn.comments.insert_one({
            "complaint_id": ObjectId(complaint_id),
            "user_id": ObjectId(current_user.id),
            "message": message,
            "created_at": helpers.now_str()
        })
        link = url_for("track_complaint", ticket_code=complaint["ticket_code"])
        # Tell the other side of the conversation, never yourself.
        if current_user.id == complaint["user_id"]:
            notify(complaint["assigned_to"],
                   "New comment on %s" % complaint["ticket_code"],
                   link, complaint_id)
        else:
            # Staff commented → email the student
            notify(complaint["user_id"],
                   "Staff replied on %s" % complaint["ticket_code"],
                   link, complaint_id)
            u_oid = ObjectId(complaint["user_id"]) if isinstance(complaint["user_id"], str) else complaint["user_id"]
            student_row = db_conn.users.find_one({"_id": u_oid})
            if student_row:
                mail.notify_comment_added(
                    student_email=student_row.get("email"),
                    student_name=student_row.get("name", "Student"),
                    ticket_code=complaint["ticket_code"],
                    commenter_name=current_user.name,
                    comment_text=message,
                )
        flash("Comment added.", "success")

    return redirect(url_for("track_complaint",
                            ticket_code=complaint["ticket_code"]))


@app.route("/complaint/<complaint_id>/feedback", methods=["POST"])
@login_required
@role_required("student")
def submit_feedback(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    if complaint["user_id"] != current_user.id:
        abort(403)
    if complaint["status"] not in ("Resolved", "Closed"):
        flash("You can rate a complaint only after it is resolved.", "warning")
        return redirect(url_for("track_complaint",
                                ticket_code=complaint["ticket_code"]))

    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0
    remark = request.form.get("remark", "").strip()

    db_conn = db.get_db()
    c_oid = ObjectId(complaint["id"]) if isinstance(complaint["id"], str) and len(complaint["id"]) == 24 else complaint["id"]
    u_oid = ObjectId(current_user.id) if isinstance(current_user.id, str) and len(current_user.id) == 24 else current_user.id

    if rating < 1 or rating > 5:
        flash("Please pick a rating between 1 and 5 stars.", "danger")
    elif db_conn.feedback.find_one({"complaint_id": c_oid}):
        flash("You have already rated this complaint.", "info")
    else:
        now = helpers.now_str()
        db_conn.feedback.insert_one({
            "complaint_id": c_oid,
            "user_id": u_oid,
            "rating": rating,
            "remark": remark,
            "created_at": now
        })
        # Rating a complaint closes it for good.
        db_conn.complaints.update_one(
            {"_id": c_oid},
            {"$set": {"status": "Closed", "rating": rating, "updated_at": now}}
        )
        db_conn.complaint_status_history.insert_one({
            "complaint_id": c_oid,
            "old_status": complaint["status"],
            "new_status": "Closed",
            "remark": f"Closed after student feedback ({rating}/5 stars).",
            "changed_by": u_oid,
            "created_at": now
        })
        flash("Thank you for your feedback.", "success")

    return redirect(url_for("track_complaint",
                            ticket_code=complaint["ticket_code"]))


@app.route("/complaint/<complaint_id>/reopen", methods=["POST"])
@login_required
@role_required("student")
def reopen_complaint(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    if complaint["user_id"] != current_user.id:
        abort(403)
    if complaint["status"] not in ("Resolved", "Closed", "Rejected"):
        flash("Only a resolved or closed complaint can be reopened.", "warning")
        return redirect(url_for("track_complaint",
                                ticket_code=complaint["ticket_code"]))

    reason = request.form.get("reason", "").strip() or "Student was not satisfied."
    reopen_count = (complaint.get("reopen_count") or 0) + 1
    now = helpers.now_str()
    new_deadline = helpers.add_days(now, complaint.get("sla_days", 5))

    db_conn = db.get_db()
    c_oid = ObjectId(complaint["id"]) if isinstance(complaint["id"], str) and len(complaint["id"]) == 24 else complaint["id"]
    u_oid = ObjectId(current_user.id) if isinstance(current_user.id, str) and len(current_user.id) == 24 else current_user.id

    new_priority = helpers.priority_score(
        complaint.get("priority_weight", 1),
        complaint["created_at"],
        reopen_count,
        complaint.get("supporter_count", 0)
    )

    db_conn.complaints.update_one(
        {"_id": c_oid},
        {"$set": {
            "status": "Reopened",
            "reopen_count": reopen_count,
            "resolved_at": None,
            "deadline": new_deadline,
            "updated_at": now,
            "priority_score": new_priority
        }}
    )

    db_conn.complaint_status_history.insert_one({
        "complaint_id": c_oid,
        "old_status": complaint["status"],
        "new_status": "Reopened",
        "remark": reason,
        "changed_by": u_oid,
        "created_at": now
    })

    link = url_for("track_complaint", ticket_code=complaint["ticket_code"])

    # Notify assigned staff
    if complaint.get("assigned_to"):
        db_conn.notifications.insert_one({
            "user_id": complaint["assigned_to"],
            "message": f"Complaint {complaint['ticket_code']} was reopened",
            "link": link,
            "is_read": False,
            "created_at": now
        })

    # Notify admins
    for admin in db_conn.users.find({"role": "admin"}):
        db_conn.notifications.insert_one({
            "user_id": admin["_id"],
            "message": f"Complaint {complaint['ticket_code']} was reopened",
            "link": link,
            "is_read": False,
            "created_at": now
        })

    # Phase 3: Multi-Reopen Automation hook
    if reopen_count >= 2:
        automation.handle_multi_reopen_escalation(db_conn, c_oid, current_user.id)
        flash("Complaint reopened. Because this is the 2nd time, it has been automatically escalated to the Principal / Dean level.", "warning")
    else:
        flash("Complaint reopened. The department has been notified.", "success")

    return redirect(link)
    return redirect(link)


# ===========================================================================
# 5. STAFF ROUTES
# ===========================================================================
@app.route("/staff")
@login_required
@role_required("staff")
def staff_dashboard():
    db_conn = db.get_db()
    staff_oid = ObjectId(current_user.id) if isinstance(current_user.id, str) else current_user.id

    cursor = db_conn.complaints.aggregate([
        {"$match": {"assigned_to": staff_oid}},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "u"}},
        {"$sort": {"created_at": -1}}
    ])

    complaints = []
    for item in cursor:
        item["id"] = str(item["_id"])
        cat = item.get("cat", [{}])[0] if item.get("cat") else {}
        u = item.get("u", [{}])[0] if item.get("u") else {}
        item["category_name"] = cat.get("name")
        item["priority_weight"] = cat.get("priority_weight", 1)
        item["student_name"] = "Anonymous Student (Identity Protected)" if item.get("is_anonymous") else u.get("name", "Student")

        # Recompute the live score, then sort most-urgent-first.
        item["live_score"] = helpers.priority_score(
            item["priority_weight"], item.get("created_at"), item.get("reopen_count", 0), item.get("supporter_count", 0)
        )
        complaints.append(item)

    complaints.sort(key=lambda item: item["live_score"], reverse=True)

    counts = {
        "total": len(complaints),
        "open": sum(1 for c in complaints
                    if c.get("status") not in config.CLOSED_STATUSES),
        "resolved": sum(1 for c in complaints
                        if c.get("status") in ("Resolved", "Closed")),
        "breached": sum(1 for c in complaints if helpers.is_breached(c)),
    }
    return render_template("staff/dashboard.html",
                           complaints=complaints, counts=counts)


@app.route("/complaint/<complaint_id>/status", methods=["GET", "POST"])
@login_required
@role_required("staff", "admin")
def update_status(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    if not can_view(complaint):
        abort(403)

    if request.method == "POST":
        new_status = request.form.get("status", "")
        remark = request.form.get("remark", "").strip()

        if new_status not in config.STATUSES:
            flash("That is not a valid status.", "danger")
            return redirect(url_for("update_status", complaint_id=complaint_id))
        if not remark:
            flash("Please add a remark explaining the change.", "danger")
            return render_template("staff/update.html", complaint=complaint)

        now = helpers.now_str()
        resolved_at = now if new_status in ("Resolved", "Closed") else None

        db_conn = db.get_db()
        c_oid = ObjectId(complaint["id"]) if isinstance(complaint["id"], str) and len(complaint["id"]) == 24 else complaint["id"]
        u_oid = ObjectId(current_user.id) if isinstance(current_user.id, str) and len(current_user.id) == 24 else current_user.id

        db_conn.complaints.update_one(
            {"_id": c_oid},
            {"$set": {
                "status": new_status,
                "updated_at": now,
                "resolved_at": resolved_at
            }}
        )

        db_conn.complaint_status_history.insert_one({
            "complaint_id": c_oid,
            "old_status": complaint["status"],
            "new_status": new_status,
            "remark": remark,
            "changed_by": u_oid,
            "created_at": now
        })

        # In-app notification
        link = url_for("track_complaint", ticket_code=complaint["ticket_code"])
        student_oid = ObjectId(complaint["user_id"]) if isinstance(complaint["user_id"], str) and len(complaint["user_id"]) == 24 else complaint["user_id"]
        notif_msg = "%s is now %s%s" % (
            complaint["ticket_code"],
            new_status,
            f" — {remark}" if remark else ""
        )
        notify(
            user_id=student_oid,
            message=notif_msg,
            link=link,
            complaint_id=c_oid,
            ticket_code=complaint["ticket_code"],
            status=new_status
        )

        # Email the student about the status change
        student_row = db_conn.users.find_one({"_id": student_oid})
        if student_row and student_row.get("email"):
            mail.notify_status_changed(
                student_email=student_row["email"],
                student_name=student_row.get("name", "Student"),
                ticket_code=complaint["ticket_code"],
                old_status=complaint["status"],
                new_status=new_status,
                remark=remark,
            )

        # Phase 3: Post-Resolution CSAT Feedback Trigger
        if new_status == "Resolved":
            automation.trigger_post_resolution_feedback(db_conn, c_oid)

        flash("Status updated to %s." % new_status, "success")
        return redirect(url_for("track_complaint",
                                ticket_code=complaint["ticket_code"]))

    return render_template("staff/update.html", complaint=complaint)


# ===========================================================================
# 6. ADMIN ROUTES
# ===========================================================================
@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    db_conn = db.get_db()
    totals = {
        "all": db_conn.complaints.count_documents({}),
        "pending": db_conn.complaints.count_documents({"status": "Pending"}),
        "in_progress": db_conn.complaints.count_documents({"status": {"$in": ["Assigned", "In Progress", "Reopened"]}}),
        "resolved": db_conn.complaints.count_documents({"status": {"$in": ["Resolved", "Closed"]}}),
    }

    # Every complaint that is still open, so we can score and flag it.
    closed_statuses = list(config.CLOSED_STATUSES)
    cursor = db_conn.complaints.aggregate([
        {"$match": {"status": {"$nin": closed_statuses}}},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "u"}},
        {"$lookup": {"from": "users", "localField": "assigned_to", "foreignField": "_id", "as": "s"}},
        {"$sort": {"created_at": -1}}
    ])

    open_rows = []
    for item in cursor:
        item["id"] = str(item["_id"])
        cat = item.get("cat", [{}])[0] if item.get("cat") else {}
        dept = item.get("dept", [{}])[0] if item.get("dept") else {}
        u = item.get("u", [{}])[0] if item.get("u") else {}
        s = item.get("s", [{}])[0] if item.get("s") else {}

        item["category_name"] = cat.get("name")
        item["priority_weight"] = cat.get("priority_weight", 1)
        item["department_name"] = dept.get("name")
        item["student_name"] = "Anonymous Student" if item.get("is_anonymous") else u.get("name", "Student")
        item["assigned_name"] = s.get("name")

        item["live_score"] = helpers.priority_score(
            item["priority_weight"], item.get("created_at"), item.get("reopen_count", 0), item.get("supporter_count", 0)
        )
        open_rows.append(item)

    # PRIORITY QUEUE -- highest score first.
    queue = sorted(open_rows, key=lambda item: item["live_score"], reverse=True)[:8]

    # SLA BREACH REPORT -- the red list.
    breached = [item for item in open_rows if helpers.is_breached(item)]
    breached.sort(key=lambda item: helpers.to_dt(item.get("deadline")) or datetime.now())

    totals["breached"] = len(breached)

    return render_template("admin/dashboard.html", totals=totals,
                           queue=queue, breached=breached[:10],
                           breached_total=len(breached))


def _build_mongo_query(filters):
    query = {}
    if filters.get("q"):
        q_reg = {"$regex": filters["q"], "$options": "i"}
        query["$or"] = [
            {"ticket_code": q_reg},
            {"subject": q_reg},
            {"description": q_reg},
        ]
    if filters.get("status") in config.STATUSES:
        query["status"] = filters["status"]
    if filters.get("category_id"):
        cid = filters["category_id"]
        query["category_id"] = ObjectId(cid) if len(cid) == 24 else cid
    if filters.get("department_id"):
        did = filters["department_id"]
        query["department_id"] = ObjectId(did) if len(did) == 24 else did
    if filters.get("date_from"):
        query.setdefault("created_at", {})["$gte"] = filters["date_from"] + " 00:00:00"
    if filters.get("date_to"):
        query.setdefault("created_at", {})["$lte"] = filters["date_to"] + " 23:59:59"
    if filters.get("breached") == "1":
        query["status"] = {"$nin": list(config.CLOSED_STATUSES)}
        query["deadline"] = {"$lt": helpers.now_str()}
    return query


def _build_where(filters):
    """Fallback compatibility shim for _build_where."""
    return "", []


@app.route("/admin/complaints")
@login_required
@role_required("admin")
def admin_complaints():
    """Searchable, filterable, paginated list of every complaint."""
    db_conn = db.get_db()
    filters = _read_filters()
    query = _build_mongo_query(filters)

    total = db_conn.complaints.count_documents(query)

    page = max(1, filters["page"])
    pages = max(1, (total + config.PAGE_SIZE - 1) // config.PAGE_SIZE)
    page = min(page, pages)
    offset = (page - 1) * config.PAGE_SIZE

    pipeline = [
        {"$match": query},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "u"}},
        {"$lookup": {"from": "users", "localField": "assigned_to", "foreignField": "_id", "as": "s"}},
        {"$sort": {"created_at": -1}},
        {"$skip": offset},
        {"$limit": config.PAGE_SIZE}
    ]

    rows = []
    for item in db_conn.complaints.aggregate(pipeline):
        item["id"] = str(item["_id"])
        cat = item.get("cat", [{}])[0] if item.get("cat") else {}
        dept = item.get("dept", [{}])[0] if item.get("dept") else {}
        u = item.get("u", [{}])[0] if item.get("u") else {}
        s = item.get("s", [{}])[0] if item.get("s") else {}

        item["category_name"] = cat.get("name")
        item["priority_weight"] = cat.get("priority_weight", 1)
        item["department_name"] = dept.get("name")
        item["student_name"] = "Anonymous Student" if item.get("is_anonymous") else u.get("name", "Student")
        item["assigned_name"] = s.get("name")
        item["live_score"] = helpers.priority_score(
            item["priority_weight"], item.get("created_at"), item.get("reopen_count", 0), item.get("supporter_count", 0)
        )
        rows.append(item)

    categories = list(db_conn.categories.find().sort("name", 1))
    for c in categories: c["id"] = str(c["_id"])
    departments = list(db_conn.departments.find().sort("name", 1))
    for d in departments: d["id"] = str(d["_id"])

    return render_template(
        "admin/complaints.html",
        complaints=rows,
        categories=categories,
        departments=departments,
        filters=filters, page=page, pages=pages, total=total,
    )


def _read_filters():
    """Pull the filter values out of the query string, with safe defaults."""
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    return {
        "q": request.args.get("q", "").strip(),
        "status": request.args.get("status", ""),
        "category_id": request.args.get("category_id", ""),
        "department_id": request.args.get("department_id", ""),
        "date_from": request.args.get("date_from", ""),
        "date_to": request.args.get("date_to", ""),
        "breached": request.args.get("breached", ""),
        "page": page,
    }


@app.route("/complaint/<complaint_id>/assign", methods=["GET", "POST"])
@login_required
@role_required("admin")
def assign_complaint(complaint_id):
    db_conn = db.get_db()
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    departments = list(db_conn.departments.find().sort("name", 1))
    for d in departments: d["id"] = str(d["_id"])

    if request.method == "POST":
        department_id = request.form.get("department_id") or None
        assigned_to = request.form.get("assigned_to") or None
        remark = request.form.get("remark", "").strip() or "Assigned by admin."

        if not assigned_to:
            flash("Please choose a staff member.", "danger")
            return redirect(url_for("assign_complaint", complaint_id=complaint_id))

        staff_oid = ObjectId(assigned_to) if len(assigned_to) == 24 else assigned_to
        staff = db_conn.users.find_one({"_id": staff_oid, "role": "staff"})
        if staff is None:
            flash("That staff member no longer exists.", "danger")
            return redirect(url_for("assign_complaint", complaint_id=complaint_id))

        now = helpers.now_str()
        dept_oid = ObjectId(department_id) if (department_id and len(department_id) == 24) else (staff.get("department_id"))
        c_oid = ObjectId(complaint_id) if len(complaint_id) == 24 else complaint_id

        db_conn.complaints.update_one(
            {"_id": c_oid},
            {"$set": {
                "department_id": dept_oid,
                "assigned_to": staff_oid,
                "status": "Assigned",
                "updated_at": now
            }}
        )

        log_status(c_oid, complaint.get("status"), "Assigned",
                   "%s (assigned to %s)" % (remark, staff.get("name")),
                   current_user.id)

        link = url_for("track_complaint", ticket_code=complaint["ticket_code"])
        notify(staff_oid,
               "You have been assigned %s" % complaint["ticket_code"],
               link, complaint_id)
        notify(complaint.get("user_id"),
               "%s has been assigned to %s" % (complaint["ticket_code"],
                                               staff.get("name")),
               link, complaint_id)

        # Email the student: their complaint is now being handled
        u_oid = ObjectId(complaint["user_id"]) if isinstance(complaint.get("user_id"), str) else complaint.get("user_id")
        student_row = db_conn.users.find_one({"_id": u_oid})
        dept_row = db_conn.departments.find_one({"_id": dept_oid}) if dept_oid else None
        if student_row:
            mail.notify_complaint_assigned(
                student_email=student_row.get("email"),
                student_name=student_row.get("name", "Student"),
                ticket_code=complaint["ticket_code"],
                department=dept_row.get("name") if dept_row else "—",
                assigned_to_name=staff.get("name"),
            )

        flash("Complaint assigned to %s." % staff.get("name"), "success")
        return redirect(url_for("admin_complaints"))

    # AUTO-ROUTING: read the text and suggest a department.
    suggested_id = helpers.suggest_department(
        complaint.get("subject"), complaint.get("description"), departments)
    suggested_name = next(
        (d["name"] for d in departments if str(d["id"]) == str(suggested_id)), None)

    staff_cursor = db_conn.users.aggregate([
        {"$match": {"role": "staff", "is_active": True}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$sort": {"name": 1}}
    ])
    staff_members = []
    for s in staff_cursor:
        s["id"] = str(s["_id"])
        dept = s.get("dept", [{}])[0] if s.get("dept") else {}
        s["department_name"] = dept.get("name")
        staff_members.append(s)

    workload_pipeline = [
        {"$match": {"assigned_to": {"$ne": None}, "status": {"$nin": list(config.CLOSED_STATUSES)}}},
        {"$group": {"_id": "$assigned_to", "n": {"$sum": 1}}}
    ]
    workload = {str(item["_id"]): item["n"] for item in db_conn.complaints.aggregate(workload_pipeline)}

    return render_template("admin/assign.html", complaint=complaint,
                           departments=departments, staff_members=staff_members,
                           suggested_id=suggested_id,
                           suggested_name=suggested_name, workload=workload)


@app.route("/admin/analytics")
@login_required
@role_required("admin")
def admin_analytics():
    db_conn = db.get_db()

    # by_status
    status_pipeline = [
        {"$group": {"_id": "$status", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}}
    ]
    by_status = [{"label": item["_id"] or "Unknown", "total": item["total"]}
                 for item in db_conn.complaints.aggregate(status_pipeline)]

    # by_category
    cat_pipeline = [
        {"$lookup": {"from": "complaints", "localField": "_id", "foreignField": "category_id", "as": "comps"}},
        {"$project": {"_id": 0, "label": "$name", "total": {"$size": "$comps"}}},
        {"$sort": {"total": -1}}
    ]
    by_category = list(db_conn.categories.aggregate(cat_pipeline))

    # by_department
    dept_pipeline = [
        {"$lookup": {"from": "complaints", "localField": "_id", "foreignField": "department_id", "as": "comps"}},
        {"$project": {"_id": 0, "label": "$name", "total": {"$size": "$comps"}}},
        {"$sort": {"total": -1}}
    ]
    by_department = list(db_conn.departments.aggregate(dept_pipeline))

    # -- average resolution time per department -----------------------------
    resolved_pipeline = [
        {"$match": {"resolved_at": {"$ne": None}}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$project": {
            "created_at": 1,
            "resolved_at": 1,
            "dept_name": {"$arrayElemAt": ["$dept.name", 0]}
        }}
    ]
    buckets = {}
    for row in db_conn.complaints.aggregate(resolved_pipeline):
        name = row.get("dept_name") or "Unassigned"
        start = helpers.to_dt(row.get("created_at"))
        end = helpers.to_dt(row.get("resolved_at"))
        if start and end:
            hours = (end - start).total_seconds() / 3600.0
            buckets.setdefault(name, []).append(hours)

    avg_resolution = sorted(
        [{"label": name,
          "days": round(sum(values) / len(values) / 24.0, 1),
          "count": len(values)}
         for name, values in buckets.items()],
        key=lambda item: item["days"], reverse=True)

    # -- SLA breaches --------------------------------------------------------
    breach_query = {
        "status": {"$nin": list(config.CLOSED_STATUSES)},
        "deadline": {"$lt": helpers.now_str()}
    }
    breach_pipeline = [
        {"$match": breach_query},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "u"}},
        {"$sort": {"deadline": 1}}
    ]
    breached = []
    for item in db_conn.complaints.aggregate(breach_pipeline):
        item["id"] = str(item["_id"])
        cat = item.get("cat", [{}])[0] if item.get("cat") else {}
        dept = item.get("dept", [{}])[0] if item.get("dept") else {}
        u = item.get("u", [{}])[0] if item.get("u") else {}
        item["category_name"] = cat.get("name")
        item["department_name"] = dept.get("name")
        item["student_name"] = u.get("name", "Student")
        breached.append(item)

    # -- monthly trend (built in Python for engine independence) -------------
    months = {}
    for doc in db_conn.complaints.find({}, {"created_at": 1}):
        moment = helpers.to_dt(doc.get("created_at"))
        if moment:
            key = moment.strftime("%Y-%m")
            months[key] = months.get(key, 0) + 1
    monthly = [{"label": key, "total": months[key]} for key in sorted(months)]

    # -- TOP RECURRING ISSUE (roadmap Step 40) -------------------------------
    top_issue = by_category[0] if by_category and by_category[0]["total"] else None

    # -- satisfaction --------------------------------------------------------
    rating_row = list(db_conn.feedback.aggregate([
        {"$group": {"_id": None, "average": {"$avg": "$rating"}, "total": {"$sum": 1}}}
    ]))
    if rating_row:
        avg_rating = round(rating_row[0]["average"] or 0, 2)
        rating_count = rating_row[0]["total"] or 0
    else:
        avg_rating = 0
        rating_count = 0

    return render_template(
        "admin/analytics.html",
        by_status=by_status, by_category=by_category,
        by_department=by_department, avg_resolution=avg_resolution,
        breached=breached, monthly=monthly, top_issue=top_issue,
        avg_rating=avg_rating, rating_count=rating_count,
    )


# ---------------------------------------------------------------------------
# Exports -- both reuse the SAME filters as the complaints list, so whatever
# the admin is looking at on screen is exactly what gets exported.
# ---------------------------------------------------------------------------
def _filtered_for_export():
    db_conn = db.get_db()
    query = _build_mongo_query(_read_filters())
    pipeline = [
        {"$match": query},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "u"}},
        {"$lookup": {"from": "users", "localField": "assigned_to", "foreignField": "_id", "as": "s"}},
        {"$sort": {"created_at": -1}}
    ]
    rows = []
    for item in db_conn.complaints.aggregate(pipeline):
        item["id"] = str(item["_id"])
        cat = item.get("cat", [{}])[0] if item.get("cat") else {}
        dept = item.get("dept", [{}])[0] if item.get("dept") else {}
        u = item.get("u", [{}])[0] if item.get("u") else {}
        s = item.get("s", [{}])[0] if item.get("s") else {}
        item["category_name"] = cat.get("name")
        item["department_name"] = dept.get("name")
        item["student_name"] = u.get("name", "Student")
        item["assigned_name"] = s.get("name")
        item["is_anonymous"] = bool(item.get("is_anonymous", False))
        item["resolved_at"] = item.get("resolved_at")
        rows.append(item)
    return rows


@app.route("/admin/export/excel")
@login_required
@role_required("admin")
def export_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    rows = _filtered_for_export()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Complaints"

    headers = ["Ticket", "Subject", "Category", "Department", "Raised By",
               "Assigned To", "Status", "Created", "Deadline", "Resolved"]
    sheet.append(headers)

    header_fill = PatternFill("solid", fgColor="1E3A5F")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row in rows:
        sheet.append([
            row.get("ticket_code"),
            row.get("subject"),
            row.get("category_name"),
            row.get("department_name") or "-",
            "Anonymous" if row.get("is_anonymous") else (row.get("student_name") or "-"),
            row.get("assigned_name") or "-",
            row.get("status"),
            helpers.pretty_date(row.get("created_at")),
            helpers.pretty_date(row.get("deadline")),
            helpers.pretty_date(row.get("resolved_at")) if row.get("resolved_at") else "-",
        ])

    for column, width in zip("ABCDEFGHIJ", [14, 42, 26, 18, 20, 18, 13, 22, 22, 22]):
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A2"

    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)

    filename = "grievance360_complaints_%s.xlsx" % datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        stream, as_attachment=True, download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet")


@app.route("/admin/export/pdf")
@login_required
@role_required("admin")
def export_pdf():
    """
    Renders a clean print-only page and triggers the browser's print dialog,
    where "Save as PDF" produces the file. This keeps the project dependency
    free and works identically on every machine in the lab.
    """
    return render_template("admin/report_print.html",
                           rows=_filtered_for_export(),
                           generated=helpers.pretty_date(helpers.now_str()))


# ===========================================================================
# 7. JSON API ROUTES (used by fetch() for live updates)
# ===========================================================================
@app.route("/api/complaint/<ticket_code>/status")
@login_required
def api_complaint_status(ticket_code):
    complaint = get_complaint_or_404(ticket_code=ticket_code)
    if not can_view(complaint):
        return jsonify({"error": "forbidden"}), 403

    from bson.objectid import ObjectId
    db_conn = db.get_db()
    cid = ObjectId(complaint["id"]) if ObjectId.is_valid(complaint.get("id", "")) else complaint.get("_id")

    pipeline = [
        {"$match": {"complaint_id": cid}},
        {"$sort": {"created_at": 1, "_id": 1}},
        {"$lookup": {"from": "users", "localField": "changed_by", "foreignField": "_id", "as": "u"}}
    ]
    history_res = list(db_conn.complaint_status_history.aggregate(pipeline))
    history_list = []
    for h in history_res:
        u_name = h.get("u", [{}])[0].get("name") if h.get("u") else "System"
        created_val = h.get("created_at")
        history_list.append({
            "old_status": h.get("old_status"),
            "new_status": h.get("new_status"),
            "status_color": helpers.status_color(h.get("new_status")),
            "remark": h.get("remark") or "",
            "changed_by_name": u_name,
            "created_at": helpers.pretty_date(created_val),
            "time_ago": helpers.time_ago(created_val),
        })

    last = history_list[-1] if history_list else None

    return jsonify({
        "ticket_code": complaint["ticket_code"],
        "status": complaint["status"],
        "status_color": helpers.status_color(complaint["status"]),
        "updated_at": helpers.pretty_date(complaint.get("updated_at")),
        "updated_time_ago": helpers.time_ago(complaint.get("updated_at")),
        "deadline": helpers.pretty_date(complaint.get("deadline")),
        "breached": helpers.is_breached(complaint),
        "days_left": helpers.days_left(complaint),
        "history_count": len(history_list),
        "history": history_list,
        "last_update": last,
    })


@app.route("/api/notifications")
@login_required
def api_notifications():
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    u_id_str = str(current_user.id)
    u_id_obj = ObjectId(u_id_str) if ObjectId.is_valid(u_id_str) else None

    or_clauses = [{"user_id": u_id_str}, {"user_id_str": u_id_str}]
    if u_id_obj:
        or_clauses.append({"user_id": u_id_obj})
    query = {"$or": or_clauses}

    rows = list(db_conn.notifications.find(query).sort("created_at", -1).limit(25))
    unread = db_conn.notifications.count_documents({**query, "is_read": False})

    items = []
    for row in rows:
        created_val = row.get("created_at")
        items.append({
            "id": str(row["_id"]),
            "message": row.get("message", ""),
            "link": row.get("link"),
            "ticket_code": row.get("ticket_code"),
            "status": row.get("status"),
            "status_color": helpers.status_color(row.get("status")) if row.get("status") else "primary",
            "is_read": bool(row.get("is_read")),
            "at": helpers.pretty_date(created_val),
            "time_ago": helpers.time_ago(created_val),
            "created_at": str(created_val) if created_val else "",
        })

    now = helpers.now_str()
    ann_match = {
        "is_active": {"$in": [1, True, "1"]},
        "starts_at": {"$lte": now},
        "ends_at": {"$gte": now},
    }
    if current_user.role != "admin":
        ann_match["$or"] = [
            {"audience_role": "all"},
            {"audience_role": current_user.role}
        ]
        
    ann_cursor = db_conn.announcements.aggregate([
        {"$match": ann_match},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$sort": {"starts_at": -1}},
        {"$limit": 5}
    ])
    announcements_list = []
    for a in ann_cursor:
        c = a.get("cat", [{}])[0] if a.get("cat") else {}
        announcements_list.append({
            "id": str(a["_id"]),
            "title": a.get("title", ""),
            "body": a.get("body", ""),
            "category_name": c.get("name", ""),
            "audience_role": a.get("audience_role", "all"),
            "starts_at": a.get("starts_at", ""),
            "ends_at": a.get("ends_at", ""),
            "pretty_ends": helpers.pretty_date(a.get("ends_at")),
            "time_ago": helpers.time_ago(a.get("created_at") or a.get("starts_at")),
            "link": url_for("announcements")
        })

    return jsonify({
        "unread": unread,
        "items": items,
        "announcements": announcements_list
    })


@app.route("/api/notifications/read", methods=["POST"])
@login_required
def api_mark_notifications_read():
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    u_id_str = str(current_user.id)
    u_id_obj = ObjectId(u_id_str) if ObjectId.is_valid(u_id_str) else None
    or_clauses = [{"user_id": u_id_str}, {"user_id_str": u_id_str}]
    if u_id_obj:
        or_clauses.append({"user_id": u_id_obj})
    db_conn.notifications.update_many({"$or": or_clauses}, {"$set": {"is_read": True}})
    return jsonify({"ok": True, "unread": 0})


@app.route("/api/notifications/<notif_id>/read", methods=["POST"])
@login_required
def api_mark_single_notification_read(notif_id):
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    if ObjectId.is_valid(notif_id):
        db_conn.notifications.update_one({"_id": ObjectId(notif_id)}, {"$set": {"is_read": True}})
    return jsonify({"ok": True})


@app.route("/api/public/notifications")
def api_public_notifications():
    """Public notification feed for guest tracking and broadcast updates."""
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    ticket_code = request.args.get("ticket_code", "").strip()
    tickets_arg = request.args.get("tickets", "").strip()
    ticket_list = []
    if ticket_code:
        ticket_list.append(ticket_code)
    if tickets_arg:
        for t in tickets_arg.split(","):
            t = t.strip()
            if t and t not in ticket_list:
                ticket_list.append(t)

    updates = []
    if ticket_list:
        complaints = list(db_conn.complaints.find({"ticket_code": {"$in": ticket_list}}))
        for c in complaints:
            cid = c.get("_id")
            last_hist = db_conn.complaint_status_history.find_one(
                {"complaint_id": cid},
                sort=[("created_at", -1)]
            )
            remark = last_hist.get("remark") if last_hist else ""
            created_val = c.get("updated_at") or c.get("created_at")
            updates.append({
                "ticket_code": c.get("ticket_code"),
                "status": c.get("status"),
                "status_color": helpers.status_color(c.get("status")),
                "remark": remark,
                "updated_at": helpers.pretty_date(created_val),
                "time_ago": helpers.time_ago(created_val),
                "message": "%s is now %s%s" % (
                    c.get("ticket_code"),
                    c.get("status"),
                    f" — {remark}" if remark else ""
                ),
                "link": f"/track/{c.get('ticket_code')}",
            })

    now = helpers.now_str()
    ann_match = {
        "is_active": {"$in": [1, True, "1"]},
        "starts_at": {"$lte": now},
        "ends_at": {"$gte": now},
        "audience_role": {"$in": ["all", "student"]}
    }
    announcements_cursor = db_conn.announcements.find(ann_match).sort("starts_at", -1).limit(5)
    ann_items = []
    for a in announcements_cursor:
        c_at = a.get("created_at") or a.get("starts_at")
        ann_items.append({
            "id": str(a.get("_id")),
            "title": a.get("title", "Campus Notice"),
            "body": a.get("body", ""),
            "message": a.get("body", ""),
            "time_ago": helpers.time_ago(c_at),
            "at": helpers.pretty_date(c_at),
            "created_at": str(c_at) if c_at else "",
            "link": url_for("announcements") if "announcements" in app.view_functions else "/announcements",
        })

    return jsonify({
        "updates": updates,
        "announcements": ann_items,
    })


@app.route("/api/public/complaint/<ticket_code>/status")
def api_public_complaint_status(ticket_code):
    """Public ticket status and timeline without exposing private student info."""
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    c = db_conn.complaints.find_one({"ticket_code": ticket_code})
    if not c:
        return jsonify({"error": "not_found"}), 404

    cid = c.get("_id")
    history_res = list(db_conn.complaint_status_history.find({"complaint_id": cid}).sort("created_at", 1))
    history_list = []
    for h in history_res:
        created_val = h.get("created_at")
        history_list.append({
            "old_status": h.get("old_status"),
            "new_status": h.get("new_status"),
            "status_color": helpers.status_color(h.get("new_status")),
            "remark": h.get("remark") or "",
            "created_at": helpers.pretty_date(created_val),
            "time_ago": helpers.time_ago(created_val),
        })

    last = history_list[-1] if history_list else None

    cat_name = "General"
    if c.get("category_id"):
        cat = db_conn.categories.find_one({"_id": c.get("category_id")})
        if cat:
            cat_name = cat.get("name", "General")

    return jsonify({
        "ticket_code": c["ticket_code"],
        "status": c["status"],
        "status_color": helpers.status_color(c["status"]),
        "category_name": cat_name,
        "subject": c.get("subject", ""),
        "updated_at": helpers.pretty_date(c.get("updated_at")),
        "updated_time_ago": helpers.time_ago(c.get("updated_at")),
        "deadline": helpers.pretty_date(c.get("deadline")),
        "breached": helpers.is_breached(c),
        "days_left": helpers.days_left(c),
        "history_count": len(history_list),
        "history": history_list,
        "last_update": last,
    })


@app.route("/track")
@app.route("/track/<ticket_code>")
def public_track_complaint(ticket_code=None):
    if not ticket_code:
        ticket_code = request.args.get("ticket", "").strip() or request.args.get("code", "").strip()
    if current_user.is_authenticated and ticket_code:
        return redirect(url_for("track_complaint", ticket_code=ticket_code))
    return render_template("track_public.html", ticket_code=ticket_code)


# ===========================================================================
# Error handlers -- these keep the user inside the app instead of on a
# default Flask stack trace.
# ===========================================================================
@app.errorhandler(403)
def error_403(error):
    return render_template("error.html", code=403,
                           message="You do not have access to that page."), 403


@app.errorhandler(404)
def error_404(error):
    return render_template("error.html", code=404,
                           message="We could not find that page."), 404


@app.errorhandler(413)
def error_413(error):
    flash("That file is too large. The maximum size is 5 MB.", "danger")
    return redirect(url_for("home_for_role"))


@app.errorhandler(500)
def error_500(error):
    app.logger.error("500 Internal Server Error: %s", error, exc_info=True)
    return render_template("error.html", code=500,
                           message="Something went wrong on our side."), 500


# ===========================================================================
# 8. M8 — ADMINISTRATION CONSOLE: users, departments, categories
# ===========================================================================

@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    q = request.args.get("q", "").strip()
    role_filter = request.args.get("role", "")
    active_filter = request.args.get("active", "")

    db_conn = db.get_db()
    query = {}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}}
        ]
    if role_filter in ("admin", "staff", "student"):
        query["role"] = role_filter
    if active_filter in ("0", "1"):
        query["is_active"] = bool(int(active_filter))

    pipeline = [
        {"$match": query},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$sort": {"role": 1, "name": 1}}
    ]
    users = []
    for u in db_conn.users.aggregate(pipeline):
        u["id"] = str(u["_id"])
        dept = u.get("dept", [{}])[0] if u.get("dept") else {}
        u["department_name"] = dept.get("name")
        users.append(u)

    return render_template("admin/users.html", users=users,
                           q=q, role=role_filter, active=active_filter)


@app.route("/admin/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_user_new():
    db_conn = db.get_db()
    departments = list(db_conn.departments.find().sort("name", 1))
    for d in departments: d["id"] = str(d["_id"])
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        role  = request.form.get("role", "staff")
        dept  = request.form.get("department_id") or None
        pwd   = request.form.get("password", "")
        errors = []
        if len(name) < 2:     errors.append("Name is required.")
        if "@" not in email:  errors.append("Valid email required.")
        if len(pwd) < 6:      errors.append("Password must be at least 6 characters.")
        if db_conn.users.find_one({"email": email}):
            errors.append("That email is already registered.")
        for e in errors: flash(e, "danger")
        if errors:
            return render_template("admin/user_form.html",
                                   user=None, departments=departments,
                                   form=request.form)
        dept_oid = ObjectId(dept) if dept and ObjectId.is_valid(dept) else None
        db_conn.users.insert_one({
            "name": name,
            "email": email,
            "phone": phone,
            "password_hash": generate_password_hash(pwd),
            "role": role,
            "department_id": dept_oid,
            "is_active": True,
            "created_at": helpers.now_str()
        })
        flash("User created.", "success")
        return redirect(url_for("admin_users"))
    return render_template("admin/user_form.html",
                           user=None, departments=departments, form={})


@app.route("/admin/users/<user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_user_edit(user_id):
    db_conn = db.get_db()
    u_oid = ObjectId(user_id) if ObjectId.is_valid(user_id) else None
    user = db_conn.users.find_one({"_id": u_oid}) if u_oid else None
    if user is None: abort(404)
    user["id"] = str(user["_id"])
    departments = list(db_conn.departments.find().sort("name", 1))
    for d in departments: d["id"] = str(d["_id"])
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        # Role change disabled for self to prevent admin lock-out
        role  = user["role"] if str(user_id) == str(current_user.id) else request.form.get("role", user["role"])
        dept  = request.form.get("department_id") or None
        dup = db_conn.users.find_one({"email": email, "_id": {"$ne": u_oid}})
        if dup: flash("That email is already in use.", "danger")
        else:
            dept_oid = ObjectId(dept) if dept and ObjectId.is_valid(dept) else None
            db_conn.users.update_one(
                {"_id": u_oid},
                {"$set": {
                    "name": name, "email": email, "phone": phone, "role": role,
                    "department_id": dept_oid
                }}
            )
            flash("User updated.", "success")
            return redirect(url_for("admin_users"))
        return render_template("admin/user_form.html",
                               user=user, departments=departments,
                               form=request.form)
    return render_template("admin/user_form.html",
                           user=user, departments=departments, form={})


@app.route("/admin/users/<user_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def admin_user_toggle(user_id):
    if str(user_id) == str(current_user.id):
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("admin_users"))
    db_conn = db.get_db()
    u_oid = ObjectId(user_id) if ObjectId.is_valid(user_id) else None
    user = db_conn.users.find_one({"_id": u_oid}) if u_oid else None
    if user is None: abort(404)
    new_state = False if user.get("is_active") else True
    db_conn.users.update_one({"_id": u_oid}, {"$set": {"is_active": new_state}})
    flash("%s %s." % (user["name"], "deactivated" if not new_state else "activated"), "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<user_id>/password", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_user_password(user_id):
    db_conn = db.get_db()
    u_oid = ObjectId(user_id) if ObjectId.is_valid(user_id) else None
    target = db_conn.users.find_one({"_id": u_oid}) if u_oid else None
    if target is None: abort(404)
    target["id"] = str(target["_id"])
    if request.method == "POST":
        pwd     = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(pwd) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif pwd != confirm:
            flash("Passwords do not match.", "danger")
        else:
            db_conn.users.update_one({"_id": u_oid}, {"$set": {"password_hash": generate_password_hash(pwd)}})
            flash("Password updated for %s." % target["name"], "success")
            return redirect(url_for("admin_users"))
    return render_template("admin/user_password.html", target_user=target)


@app.route("/admin/departments")
@login_required
@role_required("admin")
def admin_departments():
    db_conn = db.get_db()
    pipeline = [
        {"$lookup": {"from": "complaints", "localField": "_id", "foreignField": "department_id", "as": "comps"}},
        {"$project": {
            "name": 1,
            "email": 1,
            "complaint_count": {"$size": "$comps"}
        }},
        {"$sort": {"name": 1}}
    ]
    rows = []
    for d in db_conn.departments.aggregate(pipeline):
        d["id"] = str(d["_id"])
        rows.append(d)
    return render_template("admin/departments.html", departments=rows)


@app.route("/admin/departments/<dept_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_department_edit(dept_id):
    db_conn = db.get_db()
    d_oid = ObjectId(dept_id) if ObjectId.is_valid(dept_id) else None
    dept = db_conn.departments.find_one({"_id": d_oid}) if d_oid else None
    if dept is None: abort(404)
    dept["id"] = str(dept["_id"])
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        if not name: flash("Name is required.", "danger")
        else:
            db_conn.departments.update_one({"_id": d_oid}, {"$set": {"name": name, "email": email}})
            flash("Department updated.", "success")
            return redirect(url_for("admin_departments"))
    return render_template("admin/department_form.html",
                           dept=dept, form=request.form if request.method=="POST" else {})


@app.route("/admin/categories")
@login_required
@role_required("admin")
def admin_categories():
    db_conn = db.get_db()
    pipeline = [
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$sort": {"name": 1}}
    ]
    rows = []
    for c in db_conn.categories.aggregate(pipeline):
        c["id"] = str(c["_id"])
        dept = c.get("dept", [{}])[0] if c.get("dept") else {}
        c["department_name"] = dept.get("name")
        rows.append(c)
    return render_template("admin/categories.html", categories=rows)


@app.route("/admin/categories/<cat_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_category_edit(cat_id):
    db_conn = db.get_db()
    c_oid = ObjectId(cat_id) if ObjectId.is_valid(cat_id) else None
    cat = db_conn.categories.find_one({"_id": c_oid}) if c_oid else None
    if cat is None: abort(404)
    cat["id"] = str(cat["_id"])
    departments = list(db_conn.departments.find().sort("name", 1))
    for d in departments: d["id"] = str(d["_id"])
    if request.method == "POST":
        name   = request.form.get("name", "").strip()
        dept   = request.form.get("department_id") or None
        sla    = request.form.get("sla_days", "")
        weight = request.form.get("priority_weight", "")
        try:
            sla    = int(sla)
            weight = int(weight)
        except ValueError:
            flash("SLA and weight must be integers.", "danger")
            return render_template("admin/category_form.html",
                                   cat=cat, departments=departments,
                                   form=request.form)
        dept_oid = ObjectId(dept) if dept and ObjectId.is_valid(dept) else None
        db_conn.categories.update_one(
            {"_id": c_oid},
            {"$set": {
                "name": name,
                "department_id": dept_oid,
                "sla_days": sla,
                "priority_weight": weight
            }}
        )
        flash("Category updated.", "success")
        return redirect(url_for("admin_categories"))
    return render_template("admin/category_form.html",
                           cat=cat, departments=departments, form={})


# ===========================================================================
# 9. M9 — ESCALATION ENGINE
# ===========================================================================

@app.route("/admin/escalations")
@login_required
@role_required("admin")
def admin_escalations():
    db_conn = db.get_db()
    cursor = db_conn.complaints.aggregate([
        {"$match": {"status": {"$nin": list(config.CLOSED_STATUSES)}}},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$lookup": {"from": "users", "localField": "user_id", "foreignField": "_id", "as": "student"}},
        {"$lookup": {"from": "users", "localField": "assigned_to", "foreignField": "_id", "as": "assigned"}}
    ])
    open_complaints = []
    for c in cursor:
        c["id"] = str(c["_id"])
        c["category_name"] = c.get("cat", [{}])[0].get("name") if c.get("cat") else ""
        c["priority_weight"] = c.get("cat", [{}])[0].get("priority_weight", 1) if c.get("cat") else 1
        c["department_name"] = c.get("dept", [{}])[0].get("name") if c.get("dept") else ""
        c["student_name"] = c.get("student", [{}])[0].get("name") if c.get("student") else ""
        open_complaints.append(c)

    buckets = {0: [], 1: [], 2: [], 3: []}
    for c in open_complaints:
        ratio = helpers.elapsed_ratio(c)
        c["elapsed_pct"] = ratio
        lvl, _, _ = helpers.escalation_level(c)
        buckets[lvl].append(c)

    # Sort each bucket oldest-deadline-first
    for lvl in buckets:
        buckets[lvl].sort(key=lambda x: helpers.to_dt(x.get("deadline")) or datetime.now())

    levels = {k: len(v) for k, v in buckets.items()}
    sections = [
        (0, "Normal",     "secondary", buckets[0]),
        (1, "Reminder",   "info",      buckets[1]),
        (2, "Department", "warning",   buckets[2]),
        (3, "Management", "danger",    buckets[3]),
    ]
    return render_template("admin/escalations.html",
                           levels=levels, sections=sections)


@app.route("/admin/escalations/run", methods=["POST"])
@login_required
@role_required("admin")
def run_escalations():
    db_conn = db.get_db()
    sweep_res = automation.run_lifecycle_sweep(db_conn)
    raised = sweep_res.get("escalations", {}).get("escalated", 0)
    warned = sweep_res.get("sla_warnings", {}).get("pre_breach_warned", 0)
    nudged = sweep_res.get("stalled_nudges", {}).get("nudged", 0)
    flash(f"Automation sweep complete. {raised} ticket(s) escalated, {warned} SLA pre-breach warning(s), {nudged} stalled ticket nudge(s).", "success")
    return redirect(url_for("admin_escalations"))


@app.route("/api/cron/lifecycle-sweep", methods=["GET", "POST"])
def cron_lifecycle_sweep():
    """Secure endpoint for external cron triggers and automated scheduling."""
    secret = request.args.get("secret") or request.headers.get("X-Cron-Secret")
    expected_secret = os.environ.get("CRON_SECRET", "grievance360-cron-secret-key")
    if secret != expected_secret and not (current_user.is_authenticated and getattr(current_user, "role", "") == "admin"):
        return jsonify({"error": "Unauthorized"}), 401

    db_conn = db.get_db()
    res = automation.run_lifecycle_sweep(db_conn)
    return jsonify({"ok": True, "result": res})


@app.route("/api/escalation/check")
@login_required
@role_required("admin")
def api_escalation_check():
    db_conn = db.get_db()
    open_complaints = list(db_conn.complaints.find({
        "status": {"$nin": list(config.CLOSED_STATUSES)}
    }))
    counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for c in open_complaints:
        lvl, _, _ = helpers.escalation_level(c)
        counts[lvl] = counts.get(lvl, 0) + 1
    return jsonify({"levels": counts})


# ===========================================================================
# 9B. ADMIN AUTOMATION CONTROL CENTER
# ===========================================================================

@app.route("/admin/automation")
@login_required
@role_required("admin")
def admin_automation():
    db_conn = db.get_db()

    cfg = {
        "auto_assign": getattr(config, "AUTO_ASSIGN_ENABLED", True),
        "emergency_triage": getattr(config, "EMERGENCY_TRIAGE_ENABLED", True),
        "duplicate_link": getattr(config, "AUTO_DUPLICATE_LINK_ENABLED", True),
        "auto_escalation": getattr(config, "AUTO_ESCALATION_ENABLED", True),
        "auto_close_days": getattr(config, "AUTO_CLOSE_DAYS", 5),
        "sla_warning_pct": int(getattr(config, "SLA_WARNING_PERCENT", 0.75) * 100),
        "stalled_hours": getattr(config, "STALLED_TICKET_HOURS", 48),
    }

    history_cursor = db_conn.complaint_status_history.aggregate([
        {"$match": {"is_automated": True}},
        {"$sort": {"created_at": -1}},
        {"$limit": 30},
        {"$lookup": {"from": "complaints", "localField": "complaint_id", "foreignField": "_id", "as": "complaint"}},
        {"$unwind": {"path": "$complaint", "preserveNullAndEmptyArrays": True}}
    ])

    audit_logs = []
    for h in history_cursor:
        c = h.get("complaint", {})
        audit_logs.append({
            "ticket_code": c.get("ticket_code", "N/A"),
            "old_status": h.get("old_status"),
            "new_status": h.get("new_status"),
            "remark": h.get("remark"),
            "created_at": h.get("created_at")
        })

    stats = {
        "total_automated_actions": db_conn.complaint_status_history.count_documents({"is_automated": True}),
        "total_escalations": db_conn.escalations.count_documents({"is_automated": True}),
        "total_notices": db_conn.announcements.count_documents({"is_automated": True})
    }

    return render_template("admin/automation.html", config_settings=cfg, audit_logs=audit_logs, stats=stats)


@app.route("/admin/automation/settings", methods=["POST"])
@login_required
@role_required("admin")
def admin_automation_settings():
    config.AUTO_ASSIGN_ENABLED = bool(request.form.get("auto_assign"))
    config.EMERGENCY_TRIAGE_ENABLED = bool(request.form.get("emergency_triage"))
    config.AUTO_DUPLICATE_LINK_ENABLED = bool(request.form.get("duplicate_link"))
    config.AUTO_ESCALATION_ENABLED = bool(request.form.get("auto_escalation"))

    try:
        config.AUTO_CLOSE_DAYS = max(1, int(request.form.get("auto_close_days", 5)))
    except ValueError:
        pass

    try:
        config.SLA_WARNING_PERCENT = max(0.1, min(0.95, float(request.form.get("sla_warning_pct", 75)) / 100.0))
    except ValueError:
        pass

    try:
        config.STALLED_TICKET_HOURS = max(6, int(request.form.get("stalled_hours", 48)))
    except ValueError:
        pass

    flash("Automation settings updated successfully.", "success")
    return redirect(url_for("admin_automation"))


@app.route("/admin/automation/trigger/<action>", methods=["POST"])
@login_required
@role_required("admin")
def admin_automation_trigger(action):
    db_conn = db.get_db()
    if action == "sweep":
        res = automation.run_lifecycle_sweep(db_conn)
        esc = res.get("escalations", {}).get("escalated", 0)
        warn = res.get("sla_warnings", {}).get("pre_breach_warned", 0)
        closed = res.get("auto_closures", {}).get("auto_closed", 0)
        flash(f"Manual Lifecycle Sweep complete: {esc} escalated, {warn} warned, {closed} auto-closed.", "success")
    elif action == "outage":
        outages = automation.detect_campus_outage_spike(db_conn)
        if outages:
            flash(f"Outage check complete: {len(outages)} campus outage spike(s) detected and notice(s) published.", "warning")
        else:
            flash("Outage check complete: No complaint volume anomalies detected.", "info")
    elif action == "digest":
        digest = automation.generate_executive_digest(db_conn)
        flash(f"Executive digest generated and dispatched to administrators ({digest['resolution_rate']}% resolution rate).", "success")
    else:
        flash("Unknown automation action.", "danger")

    return redirect(url_for("admin_automation"))


# ===========================================================================
# 10. M10 — DUPLICATE DETECTION
# ===========================================================================

@app.route("/api/similar")
@login_required
def api_similar():
    subject     = request.args.get("subject", "").strip()
    category_id = request.args.get("category_id", "")
    if not subject or not category_id:
        return jsonify({"matches": []})

    db_conn = db.get_db()
    cat_oid = ObjectId(category_id) if ObjectId.is_valid(category_id) else category_id
    u_oid = ObjectId(current_user.id) if ObjectId.is_valid(current_user.id) else current_user.id

    query = {
        "category_id": cat_oid,
        "status": {"$nin": list(config.CLOSED_STATUSES)},
        "user_id": {"$ne": u_oid}
    }
    candidates = list(db_conn.complaints.find(query).sort("created_at", -1).limit(50))

    matches = []
    for c in candidates:
        score = helpers.similarity(subject, "", c["subject"], c.get("description") or "")
        if score >= helpers.SIMILARITY_THRESHOLD:
            matches.append({
                "ticket_code": c["ticket_code"],
                "subject": c["subject"],
                "score": round(score, 2),
                "url": url_for("track_complaint", ticket_code=c["ticket_code"]),
            })
    matches.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"matches": matches[:5]})


@app.route("/complaint/<complaint_id>/metoo", methods=["POST"])
@login_required
@role_required("student")
def endorse_complaint(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    if str(complaint.get("user_id")) == str(current_user.id):
        flash("You cannot endorse your own complaint.", "warning")
        return redirect(url_for("track_complaint",
                                ticket_code=complaint["ticket_code"]))

    db_conn = db.get_db()
    cid = ObjectId(complaint["id"]) if ObjectId.is_valid(complaint["id"]) else complaint["id"]
    uid = ObjectId(current_user.id) if ObjectId.is_valid(current_user.id) else current_user.id

    if db_conn.complaint_supporters.find_one({"complaint_id": cid, "user_id": uid}):
        flash("You have already endorsed this complaint.", "info")
    else:
        db_conn.complaint_supporters.insert_one({
            "complaint_id": cid,
            "user_id": uid,
            "supported_at": helpers.now_str()
        })
        # Refresh the priority score with the new supporter count
        supporters = db_conn.complaint_supporters.count_documents({"complaint_id": cid})
        score = helpers.priority_score(
            complaint.get("priority_weight", 1),
            complaint["created_at"],
            complaint.get("reopen_count", 0),
            supporters)
        db_conn.complaints.update_one(
            {"_id": cid},
            {"$set": {"priority_score": score, "supporter_count": supporters}}
        )
        flash("Endorsement recorded. Your support raises the complaint's priority.",
              "success")
    return redirect(url_for("track_complaint",
                            ticket_code=complaint["ticket_code"]))


@app.route("/complaint/<complaint_id>/merge", methods=["POST"])
@login_required
@role_required("admin")
def merge_complaint(complaint_id):
    child = get_complaint_or_404(complaint_id=complaint_id)
    parent_id = request.form.get("parent_id", "")
    if not parent_id:
        flash("Please provide the parent ticket ID.", "danger")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))

    db_conn = db.get_db()
    parent_query = {"ticket_code": parent_id}
    if ObjectId.is_valid(parent_id):
        parent_query = {"$or": [{"_id": ObjectId(parent_id)}, {"ticket_code": parent_id}]}
    parent = db_conn.complaints.find_one(parent_query)

    if parent is None:
        flash("Parent complaint not found.", "danger")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))
    parent["id"] = str(parent["_id"])
    if str(parent["id"]) == str(child["id"]):
        flash("A complaint cannot be merged with itself.", "danger")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))

    cid = ObjectId(child["id"]) if ObjectId.is_valid(child["id"]) else child["id"]
    if db_conn.complaint_links.find_one({"child_id": cid}):
        flash("This complaint is already merged.", "info")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))

    uid = ObjectId(current_user.id) if ObjectId.is_valid(current_user.id) else current_user.id
    db_conn.complaint_links.insert_one({
        "parent_id": parent["_id"],
        "child_id": cid,
        "linked_by": uid,
        "linked_at": helpers.now_str()
    })
    flash("Complaint %s merged into %s." % (child["ticket_code"],
                                             parent["ticket_code"]), "success")
    return redirect(url_for("track_complaint",
                            ticket_code=parent["ticket_code"]))


# ===========================================================================
# 11. M11 — KNOWLEDGE BASE
# ===========================================================================

@app.route("/kb")
@login_required
def kb_list():
    q           = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", "")
    
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    
    match_stage = {"is_published": 1}
    if q:
        match_stage["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"body": {"$regex": q, "$options": "i"}}
        ]
    if category_id:
        match_stage["category_id"] = ObjectId(category_id) if len(category_id) == 24 else category_id
        
    articles_cursor = db_conn.kb_articles.aggregate([
        {"$match": match_stage},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "c"}},
        {"$sort": {"helpful_yes": -1, "views": -1}}
    ])
    
    articles = []
    for a in articles_cursor:
        c = a.get("c", [{}])[0] if a.get("c") else {}
        a["id"] = str(a["_id"])
        a["category_name"] = c.get("name")
        articles.append(a)
        
    categories = []
    for c in db_conn.categories.find().sort("name", 1):
        c["id"] = str(c["_id"])
        categories.append(c)

    return render_template("student/kb_list.html", articles=articles,
                           categories=categories, q=q, category_id=category_id)


@app.route("/kb/<article_id>")
@login_required
def kb_article(article_id):
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    
    article_cursor = db_conn.kb_articles.aggregate([
        {"$match": {"_id": ObjectId(article_id) if len(article_id) == 24 else article_id, "is_published": 1}},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "c"}}
    ])
    
    try:
        article = next(article_cursor)
    except StopIteration:
        abort(404)
        
    c = article.get("c", [{}])[0] if article.get("c") else {}
    article["id"] = str(article["_id"])
    article["category_name"] = c.get("name")

    db_conn.kb_articles.update_one({"_id": article["_id"]}, {"$inc": {"views": 1}})
    
    already_rated = False
    if current_user.is_authenticated and current_user.role == "student":
        key = "kb_rated_%s" % article_id
        from flask import session
        already_rated = session.get(key, False)
        
    related_articles = []
    cat_match = {"category_id": article["category_id"]} if article.get("category_id") else {}
    rel_cursor = db_conn.kb_articles.find({
        **cat_match,
        "is_published": 1,
        "_id": {"$ne": article["_id"]}
    }).sort([("helpful_yes", -1), ("views", -1)]).limit(3)
    for r in rel_cursor:
        r["id"] = str(r["_id"])
        related_articles.append(r)
        
    return render_template("student/kb_article.html", article=article,
                           already_rated=already_rated,
                           related_articles=related_articles)


@app.route("/kb/<article_id>/helpful", methods=["POST"])
@login_required
def kb_helpful(article_id):
    from flask import session
    key = "kb_rated_%s" % article_id
    
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    article = db_conn.kb_articles.find_one({"_id": ObjectId(article_id) if len(article_id) == 24 else article_id, "is_published": 1})
    if article is None: abort(404)
    
    if not session.get(key):
        vote = request.form.get("vote", "no")
        col  = "helpful_yes" if vote == "yes" else "helpful_no"
        db_conn.kb_articles.update_one({"_id": article["_id"]}, {"$inc": {col: 1}})
        session[key] = True
        flash("Thank you for your feedback.", "success")
    else:
        flash("You have already rated this article.", "info")
    return redirect(url_for("kb_article", article_id=article_id))


@app.route("/kb/<article_id>/deflect", methods=["POST"])
@login_required
def kb_deflect(article_id):
    from flask import session
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    a_oid = ObjectId(article_id) if ObjectId.is_valid(article_id) else None
    if not a_oid: abort(404)
    article = db_conn.kb_articles.find_one({"_id": a_oid, "is_published": 1})
    if article is None: abort(404)
    
    key = "kb_deflected_%s" % article_id
    if not session.get(key):
        db_conn.kb_articles.update_one({"_id": a_oid}, {"$inc": {"deflections": 1, "helpful_yes": 1}})
        session[key] = True
        flash("Glad we could resolve your question without needing a complaint!", "success")
    else:
        flash("You have already confirmed this article resolved your issue.", "info")
    return redirect(url_for("kb_article", article_id=article_id))


@app.route("/api/kb/suggest")
@login_required
def api_kb_suggest():
    category_id = request.args.get("category_id", "").strip()
    q           = request.args.get("q", "").strip()
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    
    match_stage = {"is_published": 1}
    if category_id and ObjectId.is_valid(category_id):
        match_stage["category_id"] = ObjectId(category_id)
        
    if q:
        match_stage["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"body": {"$regex": q, "$options": "i"}}
        ]
        
    cursor = db_conn.kb_articles.find(match_stage).sort([("helpful_yes", -1), ("views", -1)]).limit(3)
    items = []
    for a in cursor:
        items.append({
            "id": str(a["_id"]),
            "title": a.get("title", ""),
            "url": url_for("kb_article", article_id=str(a["_id"]))
        })
    return jsonify({"items": items})


@app.route("/admin/kb")
@login_required
@role_required("admin")
def admin_kb():
    db_conn = db.get_db()
    pipeline = [
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$sort": {"is_published": -1, "helpful_yes": -1}}
    ]
    articles = []
    for a in db_conn.kb_articles.aggregate(pipeline):
        a["id"] = str(a["_id"])
        cat = a.get("cat", [{}])[0] if a.get("cat") else {}
        a["category_name"] = cat.get("name")
        articles.append(a)
    return render_template("admin/kb.html", articles=articles)


@app.route("/admin/kb/save", methods=["GET", "POST"])
@app.route("/admin/kb/save/<article_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_kb_save(article_id=None):
    db_conn = db.get_db()
    article = None
    a_oid = ObjectId(article_id) if article_id and ObjectId.is_valid(article_id) else None
    if a_oid:
        article = db_conn.kb_articles.find_one({"_id": a_oid})
        if article is None: abort(404)
        article["id"] = str(article["_id"])
    categories = list(db_conn.categories.find().sort("name", 1))
    for c in categories: c["id"] = str(c["_id"])
    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        body        = request.form.get("body", "").strip()
        category_id = request.form.get("category_id") or None
        is_published = 1 if request.form.get("is_published") else 0
        if not title or not body:
            flash("Title and body are required.", "danger")
            return render_template("admin/kb_form.html", article=article,
                                   categories=categories, form=request.form)
        cat_oid = ObjectId(category_id) if category_id and ObjectId.is_valid(category_id) else None
        if a_oid:
            db_conn.kb_articles.update_one(
                {"_id": a_oid},
                {"$set": {
                    "title": title, "body": body, "category_id": cat_oid,
                    "is_published": is_published
                }}
            )
        else:
            db_conn.kb_articles.insert_one({
                "title": title, "body": body, "category_id": cat_oid,
                "is_published": is_published, "views": 0, "helpful_yes": 0,
                "helpful_no": 0, "deflections": 0, "author_id": ObjectId(current_user.id),
                "published_at": helpers.now_str()
            })
        flash("Article saved.", "success")
        return redirect(url_for("admin_kb"))
    return render_template("admin/kb_form.html", article=article,
                           categories=categories, form={})


@app.route("/admin/kb/<article_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def admin_kb_toggle(article_id):
    db_conn = db.get_db()
    a_oid = ObjectId(article_id) if ObjectId.is_valid(article_id) else None
    article = db_conn.kb_articles.find_one({"_id": a_oid}) if a_oid else None
    if article is None: abort(404)
    new = 0 if article.get("is_published") else 1
    db_conn.kb_articles.update_one({"_id": a_oid}, {"$set": {"is_published": new}})
    flash("Article %s." % ("published" if new else "unpublished"), "success")
    return redirect(url_for("admin_kb"))


# ===========================================================================
# 12. M12 — ANNOUNCEMENTS
# ===========================================================================

@app.route("/announcements")
@login_required
def announcements():
    now = helpers.now_str()
    audience = current_user.role
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    
    match_stage = {
        "is_active": {"$in": [1, True, "1"]},
        "starts_at": {"$lte": now},
        "ends_at": {"$gte": now},
    }
    if current_user.role != "admin":
        match_stage["$or"] = [
            {"audience_role": "all"},
            {"audience_role": audience}
        ]
    
    rows_cursor = db_conn.announcements.aggregate([
        {"$match": match_stage},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "c"}},
        {"$sort": {"starts_at": -1}}
    ])
    
    rows = []
    for r in rows_cursor:
        c = r.get("c", [{}])[0] if r.get("c") else {}
        r["id"] = str(r["_id"])
        r["category_name"] = c.get("name")
        rows.append(r)
        
    return render_template("announcements.html", announcements=rows)


@app.route("/api/announcements")
@login_required
def api_announcements():
    category_id = request.args.get("category_id", "")
    now = helpers.now_str()
    audience = current_user.role
    
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    
    match_stage = {
        "is_active": {"$in": [1, True, "1"]},
        "starts_at": {"$lte": now},
        "ends_at": {"$gte": now},
    }
    if current_user.role != "admin":
        match_stage["$or"] = [
            {"audience_role": "all"},
            {"audience_role": audience}
        ]
    if category_id:
        cat_id = ObjectId(category_id) if len(category_id) == 24 else category_id
        match_stage["$and"] = [
            {"$or": [
                {"category_id": cat_id},
                {"category_id": None},
                {"category_id": ""}
            ]}
        ]
        
    rows_cursor = db_conn.announcements.find(match_stage).sort("starts_at", -1).limit(3)
    
    rows = []
    for r in rows_cursor:
        rows.append({
            "title": r.get("title"),
            "body": r.get("body")
        })
        
    return jsonify({"items": rows})


@app.route("/admin/announcements")
@login_required
@role_required("admin")
def admin_announcements():
    now = helpers.now_str()
    db_conn = db.get_db()
    pipeline = [
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$sort": {"starts_at": -1}}
    ]
    rows = []
    for a in db_conn.announcements.aggregate(pipeline):
        a["id"] = str(a["_id"])
        dept = a.get("dept", [{}])[0] if a.get("dept") else {}
        cat = a.get("cat", [{}])[0] if a.get("cat") else {}
        a["department_name"] = dept.get("name")
        a["category_name"] = cat.get("name")
        rows.append(a)
    return render_template("admin/announcements.html", announcements=rows, now=now)


@app.route("/admin/announcements/save", methods=["GET", "POST"])
@app.route("/admin/announcements/save/<ann_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_announcement_save(ann_id=None):
    from datetime import datetime, timedelta
    db_conn = db.get_db()
    ann = None
    a_oid = ObjectId(ann_id) if ann_id and ObjectId.is_valid(ann_id) else None
    if a_oid:
        ann = db_conn.announcements.find_one({"_id": a_oid})
        if ann is None: abort(404)
        ann["id"] = str(ann["_id"])
    departments = list(db_conn.departments.find().sort("name", 1))
    for d in departments: d["id"] = str(d["_id"])
    categories  = list(db_conn.categories.find().sort("name", 1))
    for c in categories: c["id"] = str(c["_id"])

    now_dt = datetime.now()
    default_starts = now_dt.strftime("%Y-%m-%dT%H:%M")
    default_ends = (now_dt + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")

    if request.method == "POST":
        title    = request.form.get("title", "").strip()
        body     = request.form.get("body", "").strip()
        audience = request.form.get("audience_role", "all")
        dept_id  = request.form.get("department_id") or None
        cat_id   = request.form.get("category_id") or None
        starts   = request.form.get("starts_at", "").strip()
        ends     = request.form.get("ends_at", "").strip()
        errors = []
        if not title: errors.append("Headline is required.")
        if not starts or not ends: errors.append("Start and end times are required.")
        if starts and ends and ends <= starts:
            errors.append("End time must be after start time.")
        for e in errors: flash(e, "danger")
        if errors:
            return render_template("admin/announcement_form.html",
                                   ann=ann, departments=departments,
                                   categories=categories, form=request.form,
                                   default_starts=default_starts, default_ends=default_ends)
        starts_clean = starts.replace("T", " ").strip()
        if len(starts_clean) == 16:
            starts_clean += ":00"
        ends_clean = ends.replace("T", " ").strip()
        if len(ends_clean) == 16:
            ends_clean += ":00"
            
        dept_oid = ObjectId(dept_id) if dept_id and ObjectId.is_valid(dept_id) else None
        cat_oid = ObjectId(cat_id) if cat_id and ObjectId.is_valid(cat_id) else None
        now_ts = helpers.now_str()

        if a_oid:
            db_conn.announcements.update_one(
                {"_id": a_oid},
                {"$set": {
                    "title": title, "body": body, "audience_role": audience,
                    "department_id": dept_oid, "category_id": cat_oid,
                    "starts_at": starts_clean, "ends_at": ends_clean
                }}
            )
        else:
            ins_res = db_conn.announcements.insert_one({
                "title": title, "body": body, "audience_role": audience,
                "department_id": dept_oid, "category_id": cat_oid,
                "starts_at": starts_clean, "ends_at": ends_clean,
                "is_active": 1, "author_id": ObjectId(current_user.id),
                "created_at": now_ts
            })
            new_ann_id = ins_res.inserted_id

            # Broadcast notifications to all users in the target audience
            target_filter = {"is_active": True}
            if audience in ("student", "staff"):
                target_filter["role"] = audience
            elif audience == "all":
                target_filter["role"] = {"$in": ["student", "staff"]}
            
            if dept_oid:
                target_filter["department_id"] = dept_oid
                
            target_users = list(db_conn.users.find(target_filter, {"_id": 1}))
            notif_docs = []
            for u in target_users:
                if str(u["_id"]) == str(current_user.id):
                    continue
                notif_docs.append({
                    "user_id": u["_id"],
                    "message": f"📢 Notice: {title}",
                    "link": "/announcements",
                    "is_read": False,
                    "created_at": now_ts,
                    "type": "announcement",
                    "announcement_id": new_ann_id
                })
            if notif_docs:
                db_conn.notifications.insert_many(notif_docs)

        flash("Announcement saved and broadcasted to campus.", "success")
        return redirect(url_for("admin_announcements"))

    return render_template("admin/announcement_form.html",
                           ann=ann, departments=departments,
                           categories=categories, form={},
                           default_starts=default_starts, default_ends=default_ends)


@app.route("/admin/announcements/<ann_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def admin_announcement_toggle(ann_id):
    db_conn = db.get_db()
    a_oid = ObjectId(ann_id) if ObjectId.is_valid(ann_id) else None
    ann = db_conn.announcements.find_one({"_id": a_oid}) if a_oid else None
    if ann is None: abort(404)
    new_state = 0 if ann.get("is_active") else 1
    db_conn.announcements.update_one({"_id": a_oid}, {"$set": {"is_active": new_state}})
    flash("Announcement %s." % ("deactivated" if not new_state else "activated"),
          "success")
    return redirect(url_for("admin_announcements"))


# ===========================================================================
# 13. M13 — STAFF PERFORMANCE SCORECARD
# ===========================================================================

def _staff_metrics(staff_id=None):
    """Compute performance metrics for one staff member or all staff."""
    db_conn = db.get_db()
    match_query = {"role": "staff"}
    if staff_id:
        match_query["_id"] = ObjectId(staff_id) if ObjectId.is_valid(staff_id) else staff_id

    pipeline = [
        {"$match": match_query},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$sort": {"name": 1}}
    ]
    staff_list = []
    for u in db_conn.users.aggregate(pipeline):
        u["id"] = str(u["_id"])
        dept = u.get("dept", [{}])[0] if u.get("dept") else {}
        u["department_name"] = dept.get("name")
        staff_list.append(u)

    results = []
    for s in staff_list:
        sid_oid = ObjectId(s["id"])

        assigned_pipeline = [
            {"$match": {"assigned_to": sid_oid}},
            {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}}
        ]
        assigned = []
        for c in db_conn.complaints.aggregate(assigned_pipeline):
            c["id"] = str(c["_id"])
            cat = c.get("cat", [{}])[0] if c.get("cat") else {}
            c["sla_days"] = cat.get("sla_days", 3)
            c["priority_weight"] = cat.get("priority_weight", 1)
            assigned.append(c)

        handled      = len(assigned)
        resolved     = [c for c in assigned if c.get("resolved_at")]
        on_time      = [c for c in resolved
                        if helpers.to_dt(c["resolved_at"]) is not None
                        and helpers.to_dt(c.get("deadline")) is not None
                        and helpers.to_dt(c["resolved_at"]) <= helpers.to_dt(c["deadline"])]
        reopen_count = sum(c.get("reopen_count", 0) or 0 for c in assigned)
        open_count   = sum(1 for c in assigned if c.get("status") not in config.CLOSED_STATUSES)
        overdue      = sum(1 for c in assigned if helpers.is_breached(c))

        avg_days = None
        if len(resolved) >= 5:  # fewer than 5 = insufficient data
            deltas = []
            for c in resolved:
                cid_oid = ObjectId(c["id"])
                assign_event = db_conn.complaint_status_history.find_one(
                    {"complaint_id": cid_oid, "new_status": "Assigned"},
                    sort=[("created_at", 1)]
                )
                start = helpers.to_dt(assign_event["created_at"]) if assign_event else helpers.to_dt(c.get("created_at"))
                end   = helpers.to_dt(c.get("resolved_at"))
                if start and end:
                    deltas.append((end - start).total_seconds() / 86400.0)
            avg_days = round(sum(deltas) / len(deltas), 1) if deltas else None

        compliance = (round(len(on_time) * 100.0 / len(resolved), 0)
                      if resolved else None)

        # ratings from feedback for complaints assigned to this staff member
        assigned_comp_ids = [ObjectId(c["id"]) for c in assigned]
        ratings_docs = list(db_conn.feedback.find({"complaint_id": {"$in": assigned_comp_ids}}))
        ratings = [r["rating"] for r in ratings_docs if r.get("rating") is not None]
        avg_rating   = round(sum(ratings) / len(ratings), 1) if ratings else None
        rating_count = len(ratings)
        reopen_rate  = (round(reopen_count * 100.0 / len(resolved), 0)
                        if resolved else None)

        results.append({
            **s,
            "handled":      handled,
            "avg_days":     avg_days,
            "compliance":   compliance,
            "avg_rating":   avg_rating,
            "rating_count": rating_count,
            "reopen_rate":  reopen_rate,
            "open_count":   open_count,
            "overdue_count": overdue,
        })
    return results


@app.route("/admin/performance")
@login_required
@role_required("admin")
def admin_performance():
    staff_rows = _staff_metrics()

    # Department rollup
    dept_map = {}
    for s in staff_rows:
        dept = s.get("department_name") or "Unassigned"
        if dept not in dept_map:
            dept_map[dept] = {"name": dept, "handled": 0, "_on_time": 0, "_total_res": 0}
        dept_map[dept]["handled"] += s["handled"]
        if s["compliance"] is not None and s["handled"]:
            resolved = s["handled"]  # rough count
            dept_map[dept]["_on_time"]    += int((s["compliance"] / 100.0) * resolved)
            dept_map[dept]["_total_res"]  += resolved
    dept_rows = []
    for d in dept_map.values():
        d["compliance"] = (round(d["_on_time"] * 100.0 / d["_total_res"], 0)
                           if d["_total_res"] else None)
        dept_rows.append(d)
    dept_rows.sort(key=lambda x: x["handled"], reverse=True)

    return render_template("admin/performance.html",
                           staff_rows=staff_rows, dept_rows=dept_rows)


@app.route("/admin/performance/<staff_id>")
@login_required
@role_required("admin")
def admin_performance_detail(staff_id):
    metrics_list = _staff_metrics(staff_id=staff_id)
    if not metrics_list: abort(404)
    metrics = metrics_list[0]

    db_conn = db.get_db()
    sid_oid = ObjectId(staff_id) if ObjectId.is_valid(staff_id) else None
    member = None
    if sid_oid:
        member_cursor = db_conn.users.aggregate([
            {"$match": {"_id": sid_oid}},
            {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}}
        ])
        member_list = list(member_cursor)
        if member_list:
            member = member_list[0]
            member["id"] = str(member["_id"])
            dept = member.get("dept", [{}])[0] if member.get("dept") else {}
            member["department_name"] = dept.get("name")
    if not member: abort(404)

    pipeline = [
        {"$match": {"assigned_to": sid_oid}},
        {"$lookup": {"from": "categories", "localField": "category_id", "foreignField": "_id", "as": "cat"}},
        {"$lookup": {"from": "departments", "localField": "department_id", "foreignField": "_id", "as": "dept"}},
        {"$sort": {"created_at": -1}}
    ]
    complaints = []
    comp_id_map = {}
    for c in db_conn.complaints.aggregate(pipeline):
        c["id"] = str(c["_id"])
        comp_id_map[c["_id"]] = c["ticket_code"]
        cat = c.get("cat", [{}])[0] if c.get("cat") else {}
        dept = c.get("dept", [{}])[0] if c.get("dept") else {}
        c["category_name"] = cat.get("name")
        c["priority_weight"] = cat.get("priority_weight", 1)
        c["department_name"] = dept.get("name")
        c["live_score"] = helpers.priority_score(
            c["priority_weight"], c["created_at"], c.get("reopen_count", 0))
        complaints.append(c)

    # Feedback ratings for complaints assigned to this staff
    assigned_cids = list(comp_id_map.keys())
    ratings = []
    for f in db_conn.feedback.find({"complaint_id": {"$in": assigned_cids}}).sort("created_at", -1).limit(20):
        f["id"] = str(f["_id"])
        f["ticket_code"] = comp_id_map.get(f.get("complaint_id"), "N/A")
        ratings.append(f)

    return render_template("admin/performance_detail.html",
                           member=member, metrics=metrics,
                           complaints=complaints, ratings=ratings)


# ===========================================================================
# M-LIVE  Live-polling JSON endpoints (no page reload needed)
# ===========================================================================

@app.route("/api/live/dashboard")
@login_required
@role_required("student")
def api_live_dashboard():
    """Student dashboard counters — polled every 20 s by live.js."""
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    rows = list(db_conn.complaints.find({"user_id": ObjectId(current_user.id)}, {"status": 1, "deadline": 1}))
    now = helpers.now_str()
    total    = len(rows)
    open_c   = sum(1 for r in rows if r.get("status") not in config.CLOSED_STATUSES)
    resolved = sum(1 for r in rows if r.get("status") in ("Resolved", "Closed"))
    breached = sum(1 for r in rows
                   if r.get("status") not in config.CLOSED_STATUSES
                   and r.get("deadline") and r["deadline"] < now)
    return jsonify(total=total, open=open_c, resolved=resolved, breached=breached)


@app.route("/api/live/admin_stats")
@login_required
@role_required("admin")
def api_live_admin_stats():
    """Admin dashboard counters — polled every 20 s by live.js."""
    db_conn = db.get_db()
    rows = list(db_conn.complaints.find({}, {"status": 1, "deadline": 1}))
    now  = helpers.now_str()
    all_c       = len(rows)
    pending     = sum(1 for r in rows if r.get("status") == "Pending")
    in_progress = sum(1 for r in rows if r.get("status") == "In Progress")
    resolved    = sum(1 for r in rows if r.get("status") in ("Resolved", "Closed"))
    breached    = sum(1 for r in rows
                      if r.get("status") not in config.CLOSED_STATUSES
                      and r.get("deadline") and r["deadline"] < now)
    return jsonify(all=all_c, pending=pending, in_progress=in_progress,
                   resolved=resolved, breached=breached)


@app.route("/api/live/staff_stats")
@login_required
@role_required("staff")
def api_live_staff_stats():
    """Staff dashboard counters — polled every 20 s by live.js."""
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    rows = list(db_conn.complaints.find({"assigned_to": ObjectId(current_user.id)}, {"status": 1, "deadline": 1}))
    now  = helpers.now_str()
    total    = len(rows)
    open_c   = sum(1 for r in rows if r.get("status") not in config.CLOSED_STATUSES)
    resolved = sum(1 for r in rows if r.get("status") in ("Resolved", "Closed"))
    breached = sum(1 for r in rows
                   if r.get("status") not in config.CLOSED_STATUSES
                   and r.get("deadline") and r["deadline"] < now)
    return jsonify(total=total, open=open_c, resolved=resolved, breached=breached)


# ===========================================================================
# M-PROFILE  Student / staff profile page
# ===========================================================================

CHARUSAT_PROGRAMS = [
    "B.Tech — Computer Engineering",
    "B.Tech — Information Technology",
    "B.Tech — Electronics & Communication",
    "B.Tech — Mechanical Engineering",
    "B.Tech — Civil Engineering",
    "B.Tech — Electrical Engineering",
    "M.Tech — Computer Engineering",
    "M.Tech — Information Technology",
    "MSc-IT",
    "MCA",
    "MBA",
    "BCA",
    "B.Pharm",
    "M.Pharm",
    "BSc — Biotechnology",
    "Other",
]

# Institutes / departments a student can belong to at CHARUSAT.
CHARUSAT_STUDENT_DEPTS = [
    "CSPIT — Chandubhai S. Patel Institute of Technology",
    "DEPSTAR — Dept. of Computer Science & Engineering & Applications",
    "PDPIAS — P. D. Patel Institute of Applied Sciences",
    "CMPICA — C. G. Patel Institute of Technology & Applied Sciences",
    "Faculty of Management Studies (FMS)",
    "Faculty of Pharmacy",
    "IQAC / Administrative & Other",
]

CHARUSAT_SEMESTERS = [
    "Semester 1",
    "Semester 2",
    "Semester 3",
    "Semester 4",
    "Semester 5",
    "Semester 6",
    "Semester 7",
    "Semester 8",
]


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    from bson.objectid import ObjectId
    db_conn = db.get_db()
    user = db_conn.users.find_one({"_id": ObjectId(current_user.id)})
    if user: user["id"] = str(user["_id"])

    if request.method == "POST":
        name               = request.form.get("name", "").strip()
        phone              = request.form.get("phone", "").strip()
        program            = request.form.get("program", "").strip()
        enrollment_no      = request.form.get("enrollment_no", "").strip()
        student_department = request.form.get("student_department", "").strip()
        semester           = request.form.get("semester", "").strip()

        errors = []
        if len(name) < 2:
            errors.append("Name must be at least 2 characters.")

        photo_name = user.get("photo") if user else None
        file = request.files.get("photo")
        if file and file.filename:
            saved, err = helpers.save_upload(file)
            if err:
                errors.append(err)
            else:
                photo_name = saved

        if errors:
            for msg in errors:
                flash(msg, "danger")
            return render_template("student/profile.html", user=user,
                                   programs=CHARUSAT_PROGRAMS,
                                   depts=CHARUSAT_STUDENT_DEPTS,
                                   semesters=CHARUSAT_SEMESTERS)

        try:
            db_conn.users.update_one(
                {"_id": ObjectId(current_user.id)},
                {"$set": {
                    "name": name, "phone": phone, "program": program, 
                    "enrollment_no": enrollment_no, "photo": photo_name,
                    "student_department": student_department, "semester": semester
                }}
            )
            flash("Profile updated successfully.", "success")
        except Exception as exc:
            app.logger.error("Failed to update profile for %s: %s", current_user.id, exc, exc_info=True)
            flash("An error occurred while saving your profile. Please try again.", "danger")
        return redirect(url_for("profile"))

    return render_template("student/profile.html", user=user,
                           programs=CHARUSAT_PROGRAMS,
                           depts=CHARUSAT_STUDENT_DEPTS,
                           semesters=CHARUSAT_SEMESTERS)


@app.route("/static/uploads/<path:filename>")
def serve_upload(filename):
    """Serve uploaded photos and attachments from local disk, /tmp, or MongoDB GridFS."""
    import tempfile
    for target_dir in [config.UPLOAD_FOLDER, os.path.join(tempfile.gettempdir(), "grievance360_uploads")]:
        local_path = os.path.join(target_dir, filename)
        if os.path.isfile(local_path):
            return send_file(local_path)

    if config.DB_ENGINE == "mongodb":
        try:
            import gridfs
            fs = gridfs.GridFS(db.get_db())
            grid_out = fs.find_one({"filename": filename})
            if grid_out:
                meta = getattr(grid_out, "metadata", {}) or {}
                content_type = meta.get("content_type") or "application/octet-stream"
                return send_file(
                    io.BytesIO(grid_out.read()),
                    mimetype=content_type,
                    download_name=filename
                )
        except Exception as exc:
            app.logger.warning("Could not fetch upload '%s' from GridFS: %s", filename, exc)

    abort(404)


@app.route("/logo/<path:filename>")
def serve_logo(filename):
    """Serve website branding assets from the logo folder."""
    for target_dir in [os.path.join(app.root_path, "logo"), os.path.join(app.root_path, "static", "logo")]:
        local_path = os.path.join(target_dir, filename)
        if os.path.isfile(local_path):
            return send_file(local_path)
    abort(404)


if __name__ == "__main__":
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    import scheduler
    scheduler.start_automation_scheduler(app, interval_seconds=getattr(config, "AUTO_ESCALATION_INTERVAL_MIN", 30) * 60)
    app.run(debug=True, host="127.0.0.1", port=5000)
