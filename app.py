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

import config
import db
import helpers
import mail

# ===========================================================================
# 1. SETUP & AUTHENTICATION PLUMBING
# ===========================================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

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
    row = db.query_one(
        "SELECT * FROM users WHERE id = %s AND is_active = 1", (user_id,)
    )
    return User(row) if row else None


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
        "priority_label": helpers.priority_label,
        "is_breached": helpers.is_breached,
        "days_left": helpers.days_left,
        "ALL_STATUSES": config.STATUSES,
        "current_year": datetime.now().year,
        "now": now,
    }


# ===========================================================================
# 2. SHARED HELPERS USED BY MANY ROUTES
# ===========================================================================
def log_status(complaint_id, old_status, new_status, remark, changed_by):
    """Write one row into the audit trail. Called on EVERY status change."""
    db.execute(
        "INSERT INTO complaint_status_history "
        "(complaint_id, old_status, new_status, remark, changed_by, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (complaint_id, old_status, new_status, remark, changed_by,
         helpers.now_str()),
    )


def notify(user_id, message, link=None, complaint_id=None):
    """Drop a notification for a user. Safe to call with user_id=None."""
    if not user_id:
        return
    db.execute(
        "INSERT INTO notifications "
        "(user_id, complaint_id, message, link, is_read, created_at) "
        "VALUES (%s, %s, %s, %s, 0, %s)",
        (user_id, complaint_id, message, link, helpers.now_str()),
    )


def get_complaint_or_404(ticket_code=None, complaint_id=None):
    """Fetch one complaint joined to the names it needs for display."""
    sql = (
        "SELECT c.*, "
        "       cat.name  AS category_name, "
        "       cat.priority_weight, "
        "       cat.sla_days, "
        "       d.name    AS department_name, "
        "       u.name    AS student_name, "
        "       u.email   AS student_email, "
        "       s.name    AS assigned_name "
        "FROM complaints c "
        "JOIN categories cat      ON cat.id = c.category_id "
        "LEFT JOIN departments d  ON d.id   = c.department_id "
        "JOIN users u             ON u.id   = c.user_id "
        "LEFT JOIN users s        ON s.id   = c.assigned_to "
    )
    if ticket_code is not None:
        row = db.query_one(sql + "WHERE c.ticket_code = %s", (ticket_code,))
    else:
        row = db.query_one(sql + "WHERE c.id = %s", (complaint_id,))
    if row is None:
        abort(404)
    return row


def can_view(complaint):
    """
    Who is allowed to open a complaint?
      admin   -> everything
      staff   -> only what is assigned to them or routed to their department
      student -> only their own
    """
    if current_user.role == "admin":
        return True
    if current_user.role == "staff":
        return (complaint["assigned_to"] == current_user.id
                or complaint["department_id"] == current_user.department_id)
    return complaint["user_id"] == current_user.id


def refresh_priority(complaint):
    """Recompute the live priority score and write it back."""
    score = helpers.priority_score(
        complaint.get("priority_weight", 1),
        complaint["created_at"],
        complaint.get("reopen_count", 0),
    )
    db.execute("UPDATE complaints SET priority_score = %s WHERE id = %s",
               (score, complaint["id"]))
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
    row = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
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

    stats = {
        "total": db.query_one("SELECT COUNT(*) AS n FROM complaints")["n"],
        "resolved": db.query_one(
            "SELECT COUNT(*) AS n FROM complaints WHERE status IN "
            "('Resolved','Closed')")["n"],
        "categories": db.query_one("SELECT COUNT(*) AS n FROM categories")["n"],
        "departments": db.query_one("SELECT COUNT(*) AS n FROM departments")["n"],
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
        if db.query_one("SELECT id FROM users WHERE email = %s", (email,)):
            errors.append("That email is already registered. Try logging in.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("register.html", form=request.form)

        db.execute(
            "INSERT INTO users "
            "(name, email, password_hash, role, enrollment_no, phone, "
            " is_active, created_at) "
            "VALUES (%s, %s, %s, 'student', %s, %s, 1, %s)",
            (name, email, generate_password_hash(password), enrollment,
             phone, helpers.now_str()),
        )
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home_for_role"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        row = db.query_one("SELECT * FROM users WHERE email = %s", (email,))
        if row and check_password_hash(row["password_hash"], password):
            if not row["is_active"]:
                flash("This account has been deactivated.", "danger")
                return render_template("login.html", email=email)
            login_user(User(row))
            flash("Welcome back, %s." % row["name"].split(" ")[0], "success")
            return redirect(url_for("home_for_role"))

        # Deliberately vague: never reveal whether the email exists.
        flash("Incorrect email or password.", "danger")
        return render_template("login.html", email=email)

    return render_template("login.html", email="")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Password reset (roadmap Step 17).
# There is no SMTP server in a college lab, so instead of emailing the link we
# show it on screen. The token logic is identical to a real email flow -- only
# the delivery differs.
# ---------------------------------------------------------------------------
@app.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    reset_link = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        row = db.query_one("SELECT id FROM users WHERE email = %s", (email,))

        if row:
            token = helpers.make_reset_token()
            expires = (datetime.now() + timedelta(hours=1)).strftime(
                helpers.DT_FORMAT)
            db.execute(
                "UPDATE users SET reset_token = %s, reset_expires = %s "
                "WHERE id = %s",
                (token, expires, row["id"]),
            )
            reset_link = url_for("reset_password", token=token, _external=True)
            flash("Reset link generated. It is valid for 1 hour.", "success")
        else:
            # Same message either way, so nobody can probe for valid emails.
            flash("If that email is registered, a reset link has been created.",
                  "info")

    return render_template("forgot.html", reset_link=reset_link)


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    row = db.query_one("SELECT * FROM users WHERE reset_token = %s", (token,))

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
            db.execute(
                "UPDATE users SET password_hash = %s, reset_token = NULL, "
                "reset_expires = NULL WHERE id = %s",
                (generate_password_hash(password), row["id"]),
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
    complaints = db.query_all(
        "SELECT c.*, cat.name AS category_name, d.name AS department_name "
        "FROM complaints c "
        "JOIN categories cat     ON cat.id = c.category_id "
        "LEFT JOIN departments d ON d.id   = c.department_id "
        "WHERE c.user_id = %s "
        "ORDER BY c.created_at DESC",
        (current_user.id,),
    )

    counts = {"total": len(complaints), "open": 0, "resolved": 0, "breached": 0}
    for item in complaints:
        if item["status"] in config.CLOSED_STATUSES:
            counts["resolved"] += 1
        else:
            counts["open"] += 1
        if helpers.is_breached(item):
            counts["breached"] += 1

    profile_missing = student_profile_missing(current_user.id)
    return render_template("student/dashboard.html",
                           complaints=complaints, counts=counts,
                           profile_missing=profile_missing)


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

    categories = db.query_all(
        "SELECT id, name, sla_days, priority_weight FROM categories ORDER BY name")

    if request.method == "POST":
        category_id = request.form.get("category_id", "")
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        is_anonymous = 1 if request.form.get("is_anonymous") else 0

        category = db.query_one(
            "SELECT * FROM categories WHERE id = %s", (category_id,))

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
        deadline = helpers.add_days(created_at, category["sla_days"])

        # The ticket code has to match the row id, so we insert with a
        # placeholder code and immediately set the real one.
        complaint_id = db.execute(
            "INSERT INTO complaints "
            "(ticket_code, user_id, category_id, department_id, subject, "
            " description, attachment, is_anonymous, status, priority_score, "
            " reopen_count, created_at, updated_at, deadline) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Pending', %s, 0, "
            "        %s, %s, %s)",
            ("PENDING", current_user.id, category["id"], category.get("department_id"),
             subject, description, attachment, is_anonymous,
             helpers.priority_score(category["priority_weight"], created_at, 0),
             created_at, created_at, deadline),
        )

        ticket_code = helpers.make_ticket_code(complaint_id - 1)
        db.execute("UPDATE complaints SET ticket_code = %s WHERE id = %s",
                   (ticket_code, complaint_id))

        log_status(complaint_id, None, "Pending",
                   "Complaint submitted by student.", current_user.id)

        # Tell every admin a new complaint landed.
        for admin in db.query_all("SELECT id FROM users WHERE role = 'admin'"):
            notify(admin["id"],
                   "New complaint %s: %s" % (ticket_code, subject[:50]),
                   url_for("track_complaint", ticket_code=ticket_code),
                   complaint_id)

        # Email confirmation to student
        student_row = db.query_one("SELECT * FROM users WHERE id = %s",
                                   (current_user.id,))
        mail.notify_complaint_submitted(
            student_email=student_row["email"],
            student_name=student_row["name"],
            ticket_code=ticket_code,
            subject=subject,
            category=category["name"],
            deadline=helpers.pretty_date(deadline),
        )

        flash("Complaint submitted. Your ticket number is %s." % ticket_code,
              "success")
        return redirect(url_for("track_complaint", ticket_code=ticket_code))

    return render_template("student/raise.html", categories=categories, form={})


@app.route("/complaint/<ticket_code>")
@login_required
def track_complaint(ticket_code):
    complaint = get_complaint_or_404(ticket_code=ticket_code)
    if not can_view(complaint):
        flash("You are not allowed to view that complaint.", "danger")
        return redirect(url_for("home_for_role"))

    history = db.query_all(
        "SELECT h.*, u.name AS changed_by_name "
        "FROM complaint_status_history h "
        "LEFT JOIN users u ON u.id = h.changed_by "
        "WHERE h.complaint_id = %s ORDER BY h.created_at ASC, h.id ASC",
        (complaint["id"],),
    )
    comments = db.query_all(
        "SELECT cm.*, u.name AS author_name, u.role AS author_role "
        "FROM comments cm JOIN users u ON u.id = cm.user_id "
        "WHERE cm.complaint_id = %s ORDER BY cm.created_at ASC",
        (complaint["id"],),
    )
    rating = db.query_one(
        "SELECT * FROM feedback WHERE complaint_id = %s", (complaint["id"],))

    return render_template("student/track.html", complaint=complaint,
                           history=history, comments=comments, rating=rating)


@app.route("/complaint/<int:complaint_id>/comment", methods=["POST"])
@login_required
def add_comment(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    if not can_view(complaint):
        abort(403)

    message = request.form.get("message", "").strip()
    if not message:
        flash("Comment cannot be empty.", "warning")
    else:
        db.execute(
            "INSERT INTO comments (complaint_id, user_id, message, created_at) "
            "VALUES (%s, %s, %s, %s)",
            (complaint_id, current_user.id, message, helpers.now_str()),
        )
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
            student_row = db.query_one(
                "SELECT email, name FROM users WHERE id = %s",
                (complaint["user_id"],))
            if student_row:
                mail.notify_comment_added(
                    student_email=student_row["email"],
                    student_name=student_row["name"],
                    ticket_code=complaint["ticket_code"],
                    commenter_name=current_user.name,
                    comment_text=message,
                )
        flash("Comment added.", "success")

    return redirect(url_for("track_complaint",
                            ticket_code=complaint["ticket_code"]))


@app.route("/complaint/<int:complaint_id>/feedback", methods=["POST"])
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

    if rating < 1 or rating > 5:
        flash("Please pick a rating between 1 and 5 stars.", "danger")
    elif db.query_one("SELECT id FROM feedback WHERE complaint_id = %s",
                      (complaint_id,)):
        flash("You have already rated this complaint.", "info")
    else:
        db.execute(
            "INSERT INTO feedback "
            "(complaint_id, user_id, rating, remark, created_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (complaint_id, current_user.id, rating, remark, helpers.now_str()),
        )
        # Rating a complaint closes it for good.
        db.execute("UPDATE complaints SET status = 'Closed', updated_at = %s "
                   "WHERE id = %s", (helpers.now_str(), complaint_id))
        log_status(complaint_id, complaint["status"], "Closed",
                   "Closed after student feedback (%d/5)." % rating,
                   current_user.id)
        flash("Thank you for your feedback.", "success")

    return redirect(url_for("track_complaint",
                            ticket_code=complaint["ticket_code"]))


@app.route("/complaint/<int:complaint_id>/reopen", methods=["POST"])
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
    reopen_count = (complaint["reopen_count"] or 0) + 1
    now = helpers.now_str()

    # Reopening restarts the SLA clock and pushes the priority score up by 5.
    new_deadline = helpers.add_days(now, complaint["sla_days"])
    db.execute(
        "UPDATE complaints SET status = 'Reopened', reopen_count = %s, "
        "resolved_at = NULL, deadline = %s, updated_at = %s WHERE id = %s",
        (reopen_count, new_deadline, now, complaint_id),
    )
    complaint["reopen_count"] = reopen_count
    refresh_priority(complaint)

    log_status(complaint_id, complaint["status"], "Reopened", reason,
               current_user.id)

    link = url_for("track_complaint", ticket_code=complaint["ticket_code"])
    notify(complaint["assigned_to"],
           "Complaint %s was reopened" % complaint["ticket_code"],
           link, complaint_id)
    for admin in db.query_all("SELECT id FROM users WHERE role = 'admin'"):
        notify(admin["id"],
               "Complaint %s was reopened" % complaint["ticket_code"],
               link, complaint_id)

    flash("Complaint reopened. The department has been notified.", "success")
    return redirect(link)


# ===========================================================================
# 5. STAFF ROUTES
# ===========================================================================
@app.route("/staff")
@login_required
@role_required("staff")
def staff_dashboard():
    complaints = db.query_all(
        "SELECT c.*, cat.name AS category_name, cat.priority_weight, "
        "       u.name AS student_name "
        "FROM complaints c "
        "JOIN categories cat ON cat.id = c.category_id "
        "JOIN users u        ON u.id   = c.user_id "
        "WHERE c.assigned_to = %s "
        "ORDER BY c.created_at DESC",
        (current_user.id,),
    )

    # Recompute the live score, then sort most-urgent-first.
    for item in complaints:
        item["live_score"] = helpers.priority_score(
            item["priority_weight"], item["created_at"], item["reopen_count"])
    complaints.sort(key=lambda item: item["live_score"], reverse=True)

    counts = {
        "total": len(complaints),
        "open": sum(1 for c in complaints
                    if c["status"] not in config.CLOSED_STATUSES),
        "resolved": sum(1 for c in complaints
                        if c["status"] in ("Resolved", "Closed")),
        "breached": sum(1 for c in complaints if helpers.is_breached(c)),
    }
    return render_template("staff/dashboard.html",
                           complaints=complaints, counts=counts)


@app.route("/complaint/<int:complaint_id>/status", methods=["GET", "POST"])
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

        db.execute(
            "UPDATE complaints SET status = %s, updated_at = %s, "
            "resolved_at = %s WHERE id = %s",
            (new_status, now, resolved_at, complaint_id),
        )
        log_status(complaint_id, complaint["status"], new_status, remark,
                   current_user.id)

        notify(complaint["user_id"],
               "%s is now %s" % (complaint["ticket_code"], new_status),
               url_for("track_complaint", ticket_code=complaint["ticket_code"]),
               complaint_id)

        # Email the student about the status change
        student_row = db.query_one("SELECT email, name FROM users WHERE id = %s",
                                   (complaint["user_id"],))
        if student_row:
            mail.notify_status_changed(
                student_email=student_row["email"],
                student_name=student_row["name"],
                ticket_code=complaint["ticket_code"],
                old_status=complaint["status"],
                new_status=new_status,
                remark=remark,
            )

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
    totals = {
        "all": db.query_one("SELECT COUNT(*) AS n FROM complaints")["n"],
        "pending": db.query_one(
            "SELECT COUNT(*) AS n FROM complaints WHERE status = 'Pending'")["n"],
        "in_progress": db.query_one(
            "SELECT COUNT(*) AS n FROM complaints WHERE status IN "
            "('Assigned','In Progress','Reopened')")["n"],
        "resolved": db.query_one(
            "SELECT COUNT(*) AS n FROM complaints WHERE status IN "
            "('Resolved','Closed')")["n"],
    }

    # Every complaint that is still open, so we can score and flag it.
    open_rows = db.query_all(
        "SELECT c.*, cat.name AS category_name, cat.priority_weight, "
        "       d.name AS department_name, u.name AS student_name, "
        "       s.name AS assigned_name "
        "FROM complaints c "
        "JOIN categories cat      ON cat.id = c.category_id "
        "LEFT JOIN departments d  ON d.id   = c.department_id "
        "JOIN users u             ON u.id   = c.user_id "
        "LEFT JOIN users s        ON s.id   = c.assigned_to "
        "WHERE c.status NOT IN ('Resolved','Closed','Rejected')"
    )
    for item in open_rows:
        item["live_score"] = helpers.priority_score(
            item["priority_weight"], item["created_at"], item["reopen_count"])

    # PRIORITY QUEUE (roadmap Step 28) -- highest score first.
    queue = sorted(open_rows, key=lambda item: item["live_score"], reverse=True)[:8]

    # SLA BREACH REPORT (roadmap Step 38) -- the red list.
    breached = [item for item in open_rows if helpers.is_breached(item)]
    breached.sort(key=lambda item: helpers.to_dt(item["deadline"]) or datetime.now())

    totals["breached"] = len(breached)

    return render_template("admin/dashboard.html", totals=totals,
                           queue=queue, breached=breached[:10],
                           breached_total=len(breached))


@app.route("/admin/complaints")
@login_required
@role_required("admin")
def admin_complaints():
    """Searchable, filterable, paginated list of every complaint."""
    filters = _read_filters()
    where_sql, params = _build_where(filters)

    total = db.query_one(
        "SELECT COUNT(*) AS n FROM complaints c "
        "JOIN categories cat ON cat.id = c.category_id "
        "JOIN users u ON u.id = c.user_id " + where_sql, params)["n"]

    page = max(1, filters["page"])
    pages = max(1, (total + config.PAGE_SIZE - 1) // config.PAGE_SIZE)
    page = min(page, pages)
    offset = (page - 1) * config.PAGE_SIZE

    rows = db.query_all(
        "SELECT c.*, cat.name AS category_name, cat.priority_weight, "
        "       d.name AS department_name, u.name AS student_name, "
        "       s.name AS assigned_name "
        "FROM complaints c "
        "JOIN categories cat      ON cat.id = c.category_id "
        "LEFT JOIN departments d  ON d.id   = c.department_id "
        "JOIN users u             ON u.id   = c.user_id "
        "LEFT JOIN users s        ON s.id   = c.assigned_to "
        + where_sql +
        " ORDER BY c.created_at DESC LIMIT %s OFFSET %s",
        params + [config.PAGE_SIZE, offset],
    )
    for item in rows:
        item["live_score"] = helpers.priority_score(
            item["priority_weight"], item["created_at"], item["reopen_count"])

    return render_template(
        "admin/complaints.html",
        complaints=rows,
        categories=db.query_all("SELECT id, name FROM categories ORDER BY name"),
        departments=db.query_all("SELECT id, name FROM departments ORDER BY name"),
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


def _build_where(filters):
    """
    Turn the filter dict into a WHERE clause plus its parameter list.

    Every value goes in as a parameter -- nothing is formatted into the SQL
    string -- so this stays injection-proof no matter what a user types.
    """
    clauses = []
    params = []

    if filters["q"]:
        clauses.append("(c.ticket_code LIKE %s OR c.subject LIKE %s "
                       "OR c.description LIKE %s OR u.name LIKE %s)")
        pattern = "%" + filters["q"] + "%"
        params.extend([pattern, pattern, pattern, pattern])

    if filters["status"] in config.STATUSES:
        clauses.append("c.status = %s")
        params.append(filters["status"])

    if filters["category_id"]:
        clauses.append("c.category_id = %s")
        params.append(filters["category_id"])

    if filters["department_id"]:
        clauses.append("c.department_id = %s")
        params.append(filters["department_id"])

    if filters["date_from"]:
        clauses.append("c.created_at >= %s")
        params.append(filters["date_from"] + " 00:00:00")

    if filters["date_to"]:
        clauses.append("c.created_at <= %s")
        params.append(filters["date_to"] + " 23:59:59")

    if filters["breached"] == "1":
        clauses.append("c.status NOT IN ('Resolved','Closed','Rejected') "
                       "AND c.deadline < %s")
        params.append(helpers.now_str())

    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


@app.route("/complaint/<int:complaint_id>/assign", methods=["GET", "POST"])
@login_required
@role_required("admin")
def assign_complaint(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    departments = db.query_all("SELECT * FROM departments ORDER BY name")

    if request.method == "POST":
        department_id = request.form.get("department_id") or None
        assigned_to = request.form.get("assigned_to") or None
        remark = request.form.get("remark", "").strip() or "Assigned by admin."

        if not assigned_to:
            flash("Please choose a staff member.", "danger")
            return redirect(url_for("assign_complaint", complaint_id=complaint_id))

        staff = db.query_one(
            "SELECT * FROM users WHERE id = %s AND role = 'staff'", (assigned_to,))
        if staff is None:
            flash("That staff member no longer exists.", "danger")
            return redirect(url_for("assign_complaint", complaint_id=complaint_id))

        now = helpers.now_str()
        db.execute(
            "UPDATE complaints SET department_id = %s, assigned_to = %s, "
            "status = 'Assigned', updated_at = %s WHERE id = %s",
            (department_id or staff["department_id"], assigned_to, now,
             complaint_id),
        )
        log_status(complaint_id, complaint["status"], "Assigned",
                   "%s (assigned to %s)" % (remark, staff["name"]),
                   current_user.id)

        link = url_for("track_complaint", ticket_code=complaint["ticket_code"])
        notify(int(assigned_to),
               "You have been assigned %s" % complaint["ticket_code"],
               link, complaint_id)
        notify(complaint["user_id"],
               "%s has been assigned to %s" % (complaint["ticket_code"],
                                               staff["name"]),
               link, complaint_id)

        # Email the student: their complaint is now being handled
        student_row = db.query_one("SELECT email, name FROM users WHERE id = %s",
                                   (complaint["user_id"],))
        dept_row = db.query_one("SELECT name FROM departments WHERE id = %s",
                                (department_id or staff["department_id"],))
        if student_row:
            mail.notify_complaint_assigned(
                student_email=student_row["email"],
                student_name=student_row["name"],
                ticket_code=complaint["ticket_code"],
                department=dept_row["name"] if dept_row else "—",
                assigned_to_name=staff["name"],
            )

        flash("Complaint assigned to %s." % staff["name"], "success")
        return redirect(url_for("admin_complaints"))

    # AUTO-ROUTING (roadmap Step 24): read the text and suggest a department.
    suggested_id = helpers.suggest_department(
        complaint["subject"], complaint["description"], departments)
    suggested_name = next(
        (d["name"] for d in departments if d["id"] == suggested_id), None)

    staff_members = db.query_all(
        "SELECT u.*, d.name AS department_name "
        "FROM users u LEFT JOIN departments d ON d.id = u.department_id "
        "WHERE u.role = 'staff' AND u.is_active = 1 ORDER BY d.name, u.name"
    )
    # How many open complaints each staff member is already carrying, so the
    # admin can avoid dumping everything on one person.
    workload = {
        row["assigned_to"]: row["n"]
        for row in db.query_all(
            "SELECT assigned_to, COUNT(*) AS n FROM complaints "
            "WHERE assigned_to IS NOT NULL "
            "AND status NOT IN ('Resolved','Closed','Rejected') "
            "GROUP BY assigned_to")
    }

    return render_template("admin/assign.html", complaint=complaint,
                           departments=departments, staff_members=staff_members,
                           suggested_id=suggested_id,
                           suggested_name=suggested_name, workload=workload)


@app.route("/admin/analytics")
@login_required
@role_required("admin")
def admin_analytics():
    by_status = db.query_all(
        "SELECT status AS label, COUNT(*) AS total FROM complaints "
        "GROUP BY status ORDER BY total DESC")

    by_category = db.query_all(
        "SELECT cat.name AS label, COUNT(c.id) AS total "
        "FROM categories cat LEFT JOIN complaints c ON c.category_id = cat.id "
        "GROUP BY cat.id, cat.name ORDER BY total DESC")

    by_department = db.query_all(
        "SELECT d.name AS label, COUNT(c.id) AS total "
        "FROM departments d LEFT JOIN complaints c ON c.department_id = d.id "
        "GROUP BY d.id, d.name ORDER BY total DESC")

    # -- average resolution time per department -----------------------------
    # Done in Python rather than TIMESTAMPDIFF/julianday so the same code runs
    # on MySQL and SQLite unchanged.
    resolved = db.query_all(
        "SELECT d.name AS label, c.created_at, c.resolved_at "
        "FROM complaints c JOIN departments d ON d.id = c.department_id "
        "WHERE c.resolved_at IS NOT NULL")

    buckets = {}
    for row in resolved:
        start = helpers.to_dt(row["created_at"])
        end = helpers.to_dt(row["resolved_at"])
        if start and end:
            hours = (end - start).total_seconds() / 3600.0
            buckets.setdefault(row["label"], []).append(hours)

    avg_resolution = sorted(
        [{"label": name,
          "days": round(sum(values) / len(values) / 24.0, 1),
          "count": len(values)}
         for name, values in buckets.items()],
        key=lambda item: item["days"], reverse=True)

    # -- SLA breaches --------------------------------------------------------
    breached = db.query_all(
        "SELECT c.*, cat.name AS category_name, d.name AS department_name, "
        "       u.name AS student_name "
        "FROM complaints c "
        "JOIN categories cat      ON cat.id = c.category_id "
        "LEFT JOIN departments d  ON d.id   = c.department_id "
        "JOIN users u             ON u.id   = c.user_id "
        "WHERE c.status NOT IN ('Resolved','Closed','Rejected') "
        "AND c.deadline < %s ORDER BY c.deadline ASC",
        (helpers.now_str(),))

    # -- monthly trend (built in Python for engine independence) -------------
    months = {}
    for row in db.query_all("SELECT created_at FROM complaints"):
        moment = helpers.to_dt(row["created_at"])
        if moment:
            key = moment.strftime("%Y-%m")
            months[key] = months.get(key, 0) + 1
    monthly = [{"label": key, "total": months[key]} for key in sorted(months)]

    # -- TOP RECURRING ISSUE (roadmap Step 40) -------------------------------
    top_issue = by_category[0] if by_category and by_category[0]["total"] else None

    # -- satisfaction --------------------------------------------------------
    rating_row = db.query_one(
        "SELECT AVG(rating) AS average, COUNT(*) AS total FROM feedback")
    avg_rating = round(rating_row["average"], 2) if rating_row["average"] else 0

    return render_template(
        "admin/analytics.html",
        by_status=by_status, by_category=by_category,
        by_department=by_department, avg_resolution=avg_resolution,
        breached=breached, monthly=monthly, top_issue=top_issue,
        avg_rating=avg_rating, rating_count=rating_row["total"] or 0,
    )


# ---------------------------------------------------------------------------
# Exports -- both reuse the SAME filters as the complaints list, so whatever
# the admin is looking at on screen is exactly what gets exported.
# ---------------------------------------------------------------------------
def _filtered_for_export():
    where_sql, params = _build_where(_read_filters())
    return db.query_all(
        "SELECT c.ticket_code, c.subject, c.status, c.created_at, c.deadline, "
        "       c.resolved_at, cat.name AS category_name, "
        "       d.name AS department_name, u.name AS student_name, "
        "       s.name AS assigned_name, c.is_anonymous "
        "FROM complaints c "
        "JOIN categories cat      ON cat.id = c.category_id "
        "LEFT JOIN departments d  ON d.id   = c.department_id "
        "JOIN users u             ON u.id   = c.user_id "
        "LEFT JOIN users s        ON s.id   = c.assigned_to "
        + where_sql + " ORDER BY c.created_at DESC", params)


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
            row["ticket_code"],
            row["subject"],
            row["category_name"],
            row["department_name"] or "-",
            "Anonymous" if row["is_anonymous"] else row["student_name"],
            row["assigned_name"] or "-",
            row["status"],
            helpers.pretty_date(row["created_at"]),
            helpers.pretty_date(row["deadline"]),
            helpers.pretty_date(row["resolved_at"]) if row["resolved_at"] else "-",
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

    last = db.query_one(
        "SELECT h.new_status, h.remark, h.created_at, u.name AS changed_by_name "
        "FROM complaint_status_history h "
        "LEFT JOIN users u ON u.id = h.changed_by "
        "WHERE h.complaint_id = %s ORDER BY h.created_at DESC, h.id DESC "
        "LIMIT 1", (complaint["id"],))

    return jsonify({
        "ticket_code": complaint["ticket_code"],
        "status": complaint["status"],
        "status_color": helpers.status_color(complaint["status"]),
        "updated_at": helpers.pretty_date(complaint["updated_at"]),
        "deadline": helpers.pretty_date(complaint["deadline"]),
        "breached": helpers.is_breached(complaint),
        "days_left": helpers.days_left(complaint),
        "history_count": db.query_one(
            "SELECT COUNT(*) AS n FROM complaint_status_history "
            "WHERE complaint_id = %s", (complaint["id"],))["n"],
        "last_update": {
            "status": last["new_status"],
            "remark": last["remark"],
            "by": last["changed_by_name"],
            "at": helpers.pretty_date(last["created_at"]),
        } if last else None,
    })


@app.route("/api/notifications")
@login_required
def api_notifications():
    rows = db.query_all(
        "SELECT * FROM notifications WHERE user_id = %s "
        "ORDER BY created_at DESC, id DESC LIMIT 10", (current_user.id,))
    unread = db.query_one(
        "SELECT COUNT(*) AS n FROM notifications "
        "WHERE user_id = %s AND is_read = 0", (current_user.id,))["n"]

    return jsonify({
        "unread": unread,
        "items": [{
            "id": row["id"],
            "message": row["message"],
            "link": row["link"],
            "is_read": bool(row["is_read"]),
            "at": helpers.pretty_date(row["created_at"]),
        } for row in rows],
    })


@app.route("/api/notifications/read", methods=["POST"])
@login_required
def api_mark_notifications_read():
    db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s",
               (current_user.id,))
    return jsonify({"ok": True, "unread": 0})


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

    clauses, params = [], []
    if q:
        clauses.append("(u.name LIKE %s OR u.email LIKE %s)")
        p = "%" + q + "%"
        params.extend([p, p])
    if role_filter in ("admin", "staff", "student"):
        clauses.append("u.role = %s"); params.append(role_filter)
    if active_filter in ("0", "1"):
        clauses.append("u.is_active = %s"); params.append(int(active_filter))

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    users = db.query_all(
        "SELECT u.*, d.name AS department_name "
        "FROM users u LEFT JOIN departments d ON d.id = u.department_id"
        + where + " ORDER BY u.role, u.name", params)
    return render_template("admin/users.html", users=users,
                           q=q, role=role_filter, active=active_filter)


@app.route("/admin/users/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_user_new():
    departments = db.query_all("SELECT id, name FROM departments ORDER BY name")
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
        if db.query_one("SELECT id FROM users WHERE email = %s", (email,)):
            errors.append("That email is already registered.")
        for e in errors: flash(e, "danger")
        if errors:
            return render_template("admin/user_form.html",
                                   user=None, departments=departments,
                                   form=request.form)
        db.execute(
            "INSERT INTO users (name, email, phone, password_hash, role, "
            "department_id, is_active, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, 1, %s)",
            (name, email, phone, generate_password_hash(pwd),
             role, dept, helpers.now_str()))
        flash("User created.", "success")
        return redirect(url_for("admin_users"))
    return render_template("admin/user_form.html",
                           user=None, departments=departments, form={})


@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_user_edit(user_id):
    user = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if user is None: abort(404)
    departments = db.query_all("SELECT id, name FROM departments ORDER BY name")
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        # Role change disabled for self to prevent admin lock-out
        role  = user["role"] if user_id == current_user.id else request.form.get("role", user["role"])
        dept  = request.form.get("department_id") or None
        dup = db.query_one("SELECT id FROM users WHERE email = %s AND id != %s",
                           (email, user_id))
        if dup: flash("That email is already in use.", "danger")
        else:
            db.execute(
                "UPDATE users SET name=%s, email=%s, phone=%s, role=%s, "
                "department_id=%s WHERE id=%s",
                (name, email, phone, role, dept, user_id))
            flash("User updated.", "success")
            return redirect(url_for("admin_users"))
        return render_template("admin/user_form.html",
                               user=user, departments=departments,
                               form=request.form)
    return render_template("admin/user_form.html",
                           user=user, departments=departments, form={})


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def admin_user_toggle(user_id):
    if user_id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("admin_users"))
    user = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if user is None: abort(404)
    new_state = 0 if user["is_active"] else 1
    db.execute("UPDATE users SET is_active=%s WHERE id=%s", (new_state, user_id))
    flash("%s %s." % (user["name"], "deactivated" if not new_state else "activated"), "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/password", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_user_password(user_id):
    target = db.query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if target is None: abort(404)
    if request.method == "POST":
        pwd     = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(pwd) < 6:
            flash("Password must be at least 6 characters.", "danger")
        elif pwd != confirm:
            flash("Passwords do not match.", "danger")
        else:
            db.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                       (generate_password_hash(pwd), user_id))
            flash("Password updated for %s." % target["name"], "success")
            return redirect(url_for("admin_users"))
    return render_template("admin/user_password.html", target_user=target)


@app.route("/admin/departments")
@login_required
@role_required("admin")
def admin_departments():
    rows = db.query_all(
        "SELECT d.*, COUNT(c.id) AS complaint_count "
        "FROM departments d "
        "LEFT JOIN complaints c ON c.department_id = d.id "
        "GROUP BY d.id ORDER BY d.name")
    return render_template("admin/departments.html", departments=rows)


@app.route("/admin/departments/<int:dept_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_department_edit(dept_id):
    dept = db.query_one("SELECT * FROM departments WHERE id = %s", (dept_id,))
    if dept is None: abort(404)
    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        if not name: flash("Name is required.", "danger")
        else:
            db.execute("UPDATE departments SET name=%s, email=%s WHERE id=%s",
                       (name, email, dept_id))
            flash("Department updated.", "success")
            return redirect(url_for("admin_departments"))
    return render_template("admin/department_form.html",
                           dept=dept, form=request.form if request.method=="POST" else {})


@app.route("/admin/categories")
@login_required
@role_required("admin")
def admin_categories():
    rows = db.query_all(
        "SELECT c.*, d.name AS department_name "
        "FROM categories c LEFT JOIN departments d ON d.id = c.department_id "
        "ORDER BY c.name")
    return render_template("admin/categories.html", categories=rows)


@app.route("/admin/categories/<int:cat_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_category_edit(cat_id):
    cat = db.query_one("SELECT * FROM categories WHERE id = %s", (cat_id,))
    if cat is None: abort(404)
    departments = db.query_all("SELECT id, name FROM departments ORDER BY name")
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
        db.execute(
            "UPDATE categories SET name=%s, department_id=%s, "
            "sla_days=%s, priority_weight=%s WHERE id=%s",
            (name, dept, sla, weight, cat_id))
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
    open_complaints = db.query_all(
        "SELECT c.*, cat.name AS category_name, cat.priority_weight, "
        "       d.name AS department_name, u.name AS student_name "
        "FROM complaints c "
        "JOIN categories cat      ON cat.id = c.category_id "
        "LEFT JOIN departments d  ON d.id   = c.department_id "
        "JOIN users u             ON u.id   = c.user_id "
        "WHERE c.status NOT IN ('Resolved','Closed','Rejected')"
    )

    buckets = {0: [], 1: [], 2: [], 3: []}
    for c in open_complaints:
        ratio = helpers.elapsed_ratio(c)
        c["elapsed_pct"] = ratio
        lvl, _, _ = helpers.escalation_level(c)
        buckets[lvl].append(c)

    # Sort each bucket oldest-deadline-first
    for lvl in buckets:
        buckets[lvl].sort(key=lambda x: helpers.to_dt(x["deadline"]) or datetime.now())

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
    open_complaints = db.query_all(
        "SELECT c.*, cat.sla_days, cat.priority_weight "
        "FROM complaints c "
        "JOIN categories cat ON cat.id = c.category_id "
        "WHERE c.status NOT IN ('Resolved','Closed','Rejected')"
    )
    admins = db.query_all("SELECT id FROM users WHERE role = 'admin'")
    raised = 0
    for c in open_complaints:
        lvl, label, _ = helpers.escalation_level(c)
        if lvl == 0:
            continue
        existing = db.query_one(
            "SELECT to_level FROM escalations WHERE complaint_id = %s "
            "ORDER BY to_level DESC LIMIT 1", (c["id"],))
        current_top = existing["to_level"] if existing else 0
        if lvl <= current_top:
            continue  # escalation only moves up
        ratio = helpers.elapsed_ratio(c)
        reason = "Elapsed ratio %.2f — %s threshold crossed." % (ratio, label)
        # Notify assigned staff for level 1, all admins for 2+
        notify_ids = []
        if lvl == 1 and c.get("assigned_to"):
            notify_ids = [c["assigned_to"]]
        elif lvl >= 2:
            notify_ids = [a["id"] for a in admins]
        student_row = db.query_one(
            "SELECT name FROM users WHERE id = %s", (c["user_id"],))
        student_name = student_row["name"] if student_row else "Unknown"

        for uid in notify_ids:
            db.execute(
                "INSERT INTO escalations "
                "(complaint_id, from_level, to_level, reason, "
                "notified_user_id, escalated_at) VALUES (%s,%s,%s,%s,%s,%s)",
                (c["id"], current_top, lvl, reason, uid, helpers.now_str()))
            link = url_for("track_complaint", ticket_code=c["ticket_code"])
            notify(uid, "Complaint %s escalated to %s" % (c["ticket_code"], label),
                   link, c["id"])
            # Email the notified admin / staff member
            notif_user = db.query_one("SELECT email FROM users WHERE id = %s",
                                      (uid,))
            if notif_user:
                mail.notify_escalation(
                    admin_email=notif_user["email"],
                    ticket_code=c["ticket_code"],
                    subject=c["subject"],
                    level_label=label,
                    student_name=student_name,
                )
        raised += 1
    flash("Sweep complete. %d complaint(s) escalated." % raised, "success")
    return redirect(url_for("admin_escalations"))


@app.route("/api/escalation/check")
@login_required
@role_required("admin")
def api_escalation_check():
    open_complaints = db.query_all(
        "SELECT c.*, cat.priority_weight FROM complaints c "
        "JOIN categories cat ON cat.id = c.category_id "
        "WHERE c.status NOT IN ('Resolved','Closed','Rejected')"
    )
    counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for c in open_complaints:
        lvl, _, _ = helpers.escalation_level(c)
        counts[lvl] = counts.get(lvl, 0) + 1
    return jsonify({"levels": counts})


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

    candidates = db.query_all(
        "SELECT id, ticket_code, subject, description "
        "FROM complaints "
        "WHERE category_id = %s "
        "AND status NOT IN ('Resolved','Closed','Rejected') "
        "AND user_id != %s "
        "ORDER BY created_at DESC LIMIT 50",
        (category_id, current_user.id))

    matches = []
    for c in candidates:
        score = helpers.similarity(subject, "", c["subject"], c["description"] or "")
        if score >= helpers.SIMILARITY_THRESHOLD:
            matches.append({
                "ticket_code": c["ticket_code"],
                "subject": c["subject"],
                "score": round(score, 2),
                "url": url_for("track_complaint", ticket_code=c["ticket_code"]),
            })
    matches.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"matches": matches[:5]})


@app.route("/complaint/<int:complaint_id>/metoo", methods=["POST"])
@login_required
@role_required("student")
def endorse_complaint(complaint_id):
    complaint = get_complaint_or_404(complaint_id=complaint_id)
    if complaint["user_id"] == current_user.id:
        flash("You cannot endorse your own complaint.", "warning")
        return redirect(url_for("track_complaint",
                                ticket_code=complaint["ticket_code"]))
    if db.query_one(
            "SELECT id FROM complaint_supporters "
            "WHERE complaint_id=%s AND user_id=%s",
            (complaint_id, current_user.id)):
        flash("You have already endorsed this complaint.", "info")
    else:
        db.execute(
            "INSERT INTO complaint_supporters "
            "(complaint_id, user_id, supported_at) VALUES (%s,%s,%s)",
            (complaint_id, current_user.id, helpers.now_str()))
        # Refresh the priority score with the new supporter count
        supporters = db.query_one(
            "SELECT COUNT(*) AS n FROM complaint_supporters WHERE complaint_id=%s",
            (complaint_id,))["n"]
        score = helpers.priority_score(
            complaint.get("priority_weight", 1),
            complaint["created_at"],
            complaint.get("reopen_count", 0),
            supporters)
        db.execute("UPDATE complaints SET priority_score=%s WHERE id=%s",
                   (score, complaint_id))
        flash("Endorsement recorded. Your support raises the complaint's priority.",
              "success")
    return redirect(url_for("track_complaint",
                            ticket_code=complaint["ticket_code"]))


@app.route("/complaint/<int:complaint_id>/merge", methods=["POST"])
@login_required
@role_required("admin")
def merge_complaint(complaint_id):
    child = get_complaint_or_404(complaint_id=complaint_id)
    parent_id = request.form.get("parent_id", "")
    if not parent_id:
        flash("Please provide the parent ticket ID.", "danger")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))
    parent = db.query_one(
        "SELECT * FROM complaints WHERE id=%s OR ticket_code=%s",
        (parent_id, parent_id))
    if parent is None:
        flash("Parent complaint not found.", "danger")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))
    if parent["id"] == complaint_id:
        flash("A complaint cannot be merged with itself.", "danger")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))
    if db.query_one("SELECT id FROM complaint_links WHERE child_id=%s",
                    (complaint_id,)):
        flash("This complaint is already merged.", "info")
        return redirect(url_for("track_complaint",
                                ticket_code=child["ticket_code"]))
    db.execute(
        "INSERT INTO complaint_links "
        "(parent_id, child_id, linked_by, linked_at) VALUES (%s,%s,%s,%s)",
        (parent["id"], complaint_id, current_user.id, helpers.now_str()))
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
    clauses, params = ["is_published = 1"], []
    if q:
        clauses.append("(title LIKE %s OR body LIKE %s)")
        p = "%" + q + "%"; params.extend([p, p])
    if category_id:
        clauses.append("category_id = %s"); params.append(category_id)
    articles = db.query_all(
        "SELECT a.*, c.name AS category_name "
        "FROM kb_articles a LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE " + " AND ".join(clauses) +
        " ORDER BY a.helpful_yes DESC, a.views DESC", params)
    categories = db.query_all("SELECT id, name FROM categories ORDER BY name")
    return render_template("student/kb_list.html", articles=articles,
                           categories=categories, q=q, category_id=category_id)


@app.route("/kb/<int:article_id>")
@login_required
def kb_article(article_id):
    article = db.query_one(
        "SELECT a.*, c.name AS category_name "
        "FROM kb_articles a LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE a.id = %s AND a.is_published = 1", (article_id,))
    if article is None: abort(404)
    db.execute("UPDATE kb_articles SET views = views + 1 WHERE id=%s",
               (article_id,))
    already_rated = False
    if current_user.is_authenticated and current_user.role == "student":
        # Check session-level flag (SQLite has no per-user helpful table)
        key = "kb_rated_%d" % article_id
        from flask import session
        already_rated = session.get(key, False)
    return render_template("student/kb_article.html", article=article,
                           already_rated=already_rated)


@app.route("/kb/<int:article_id>/helpful", methods=["POST"])
@login_required
def kb_helpful(article_id):
    from flask import session
    key = "kb_rated_%d" % article_id
    article = db.query_one("SELECT id FROM kb_articles WHERE id=%s AND is_published=1",
                           (article_id,))
    if article is None: abort(404)
    if not session.get(key):
        vote = request.form.get("vote", "no")
        col  = "helpful_yes" if vote == "yes" else "helpful_no"
        db.execute("UPDATE kb_articles SET %s = %s + 1 WHERE id=%s" % (col, col, "%s"),
                   (article_id,))
        session[key] = True
        flash("Thank you for your feedback.", "success")
    else:
        flash("You have already rated this article.", "info")
    return redirect(url_for("kb_article", article_id=article_id))


@app.route("/admin/kb")
@login_required
@role_required("admin")
def admin_kb():
    articles = db.query_all(
        "SELECT a.*, c.name AS category_name "
        "FROM kb_articles a LEFT JOIN categories c ON c.id = a.category_id "
        "ORDER BY a.is_published DESC, a.helpful_yes DESC")
    return render_template("admin/kb.html", articles=articles)


@app.route("/admin/kb/save", methods=["GET", "POST"])
@app.route("/admin/kb/save/<int:article_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_kb_save(article_id=None):
    article = None
    if article_id:
        article = db.query_one("SELECT * FROM kb_articles WHERE id=%s",
                               (article_id,))
        if article is None: abort(404)
    categories = db.query_all("SELECT id, name FROM categories ORDER BY name")
    if request.method == "POST":
        title       = request.form.get("title", "").strip()
        body        = request.form.get("body", "").strip()
        category_id = request.form.get("category_id") or None
        is_published = 1 if request.form.get("is_published") else 0
        if not title or not body:
            flash("Title and body are required.", "danger")
            return render_template("admin/kb_form.html", article=article,
                                   categories=categories, form=request.form)
        if article_id:
            db.execute(
                "UPDATE kb_articles SET title=%s, body=%s, category_id=%s, "
                "is_published=%s WHERE id=%s",
                (title, body, category_id, is_published, article_id))
        else:
            db.execute(
                "INSERT INTO kb_articles "
                "(title, body, category_id, is_published, views, helpful_yes, "
                "helpful_no, deflections, author_id, published_at) "
                "VALUES (%s,%s,%s,%s,0,0,0,0,%s,%s)",
                (title, body, category_id, is_published,
                 current_user.id, helpers.now_str()))
        flash("Article saved.", "success")
        return redirect(url_for("admin_kb"))
    return render_template("admin/kb_form.html", article=article,
                           categories=categories, form={})


@app.route("/admin/kb/<int:article_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def admin_kb_toggle(article_id):
    article = db.query_one("SELECT * FROM kb_articles WHERE id=%s", (article_id,))
    if article is None: abort(404)
    new = 0 if article["is_published"] else 1
    db.execute("UPDATE kb_articles SET is_published=%s WHERE id=%s",
               (new, article_id))
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
    rows = db.query_all(
        "SELECT a.*, c.name AS category_name "
        "FROM announcements a "
        "LEFT JOIN categories c ON c.id = a.category_id "
        "WHERE a.is_active = 1 "
        "AND a.starts_at <= %s AND a.ends_at >= %s "
        "AND (a.audience_role = 'all' OR a.audience_role = %s) "
        "ORDER BY a.starts_at DESC",
        (now, now, audience))
    return render_template("announcements.html", announcements=rows)


@app.route("/api/announcements")
@login_required
def api_announcements():
    category_id = request.args.get("category_id", "")
    now = helpers.now_str()
    audience = current_user.role
    clauses = [
        "a.is_active = 1",
        "a.starts_at <= %s", "a.ends_at >= %s",
        "(a.audience_role = 'all' OR a.audience_role = %s)",
    ]
    params = [now, now, audience]
    if category_id:
        clauses.append("(a.category_id = %s OR a.category_id IS NULL)")
        params.append(category_id)
    rows = db.query_all(
        "SELECT a.title, a.body "
        "FROM announcements a WHERE " + " AND ".join(clauses) +
        " ORDER BY a.starts_at DESC LIMIT 3", params)
    return jsonify({"items": [dict(r) for r in rows]})


@app.route("/admin/announcements")
@login_required
@role_required("admin")
def admin_announcements():
    now = helpers.now_str()
    rows = db.query_all(
        "SELECT a.*, d.name AS department_name, c.name AS category_name "
        "FROM announcements a "
        "LEFT JOIN departments d ON d.id = a.department_id "
        "LEFT JOIN categories c ON c.id = a.category_id "
        "ORDER BY a.starts_at DESC")
    return render_template("admin/announcements.html", announcements=rows, now=now)


@app.route("/admin/announcements/save", methods=["GET", "POST"])
@app.route("/admin/announcements/save/<int:ann_id>", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_announcement_save(ann_id=None):
    ann = None
    if ann_id:
        ann = db.query_one("SELECT * FROM announcements WHERE id=%s", (ann_id,))
        if ann is None: abort(404)
    departments = db.query_all("SELECT id, name FROM departments ORDER BY name")
    categories  = db.query_all("SELECT id, name FROM categories ORDER BY name")
    if request.method == "POST":
        title    = request.form.get("title", "").strip()
        body     = request.form.get("body", "").strip()
        audience = request.form.get("audience_role", "all")
        dept_id  = request.form.get("department_id") or None
        cat_id   = request.form.get("category_id") or None
        starts   = request.form.get("starts_at", "")
        ends     = request.form.get("ends_at", "")
        errors = []
        if not title: errors.append("Headline is required.")
        if not starts or not ends: errors.append("Start and end times are required.")
        if starts and ends and ends <= starts:
            errors.append("End time must be after start time.")
        for e in errors: flash(e, "danger")
        if errors:
            return render_template("admin/announcement_form.html",
                                   ann=ann, departments=departments,
                                   categories=categories, form=request.form)
        # Convert datetime-local format to storage format
        starts_dt = starts.replace("T", " ") + ":00" if len(starts) == 16 else starts
        ends_dt   = ends.replace("T", " ") + ":00"   if len(ends)   == 16 else ends
        if ann_id:
            db.execute(
                "UPDATE announcements SET title=%s, body=%s, audience_role=%s, "
                "department_id=%s, category_id=%s, starts_at=%s, ends_at=%s "
                "WHERE id=%s",
                (title, body, audience, dept_id, cat_id,
                 starts_dt, ends_dt, ann_id))
        else:
            db.execute(
                "INSERT INTO announcements "
                "(title, body, audience_role, department_id, category_id, "
                "starts_at, ends_at, is_active, author_id) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)",
                (title, body, audience, dept_id, cat_id,
                 starts_dt, ends_dt, current_user.id))
        flash("Announcement saved.", "success")
        return redirect(url_for("admin_announcements"))
    return render_template("admin/announcement_form.html",
                           ann=ann, departments=departments,
                           categories=categories, form={})


@app.route("/admin/announcements/<int:ann_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def admin_announcement_toggle(ann_id):
    ann = db.query_one("SELECT * FROM announcements WHERE id=%s", (ann_id,))
    if ann is None: abort(404)
    db.execute("UPDATE announcements SET is_active=%s WHERE id=%s",
               (0 if ann["is_active"] else 1, ann_id))
    flash("Announcement %s." % ("deactivated" if ann["is_active"] else "activated"),
          "success")
    return redirect(url_for("admin_announcements"))


# ===========================================================================
# 13. M13 — STAFF PERFORMANCE SCORECARD
# ===========================================================================

def _staff_metrics(staff_id=None):
    """Compute performance metrics for one staff member or all staff."""
    where = "WHERE u.role = 'staff'"
    params = []
    if staff_id:
        where += " AND u.id = %s"; params.append(staff_id)

    staff_list = db.query_all(
        "SELECT u.id, u.name, u.email, d.name AS department_name "
        "FROM users u LEFT JOIN departments d ON d.id = u.department_id "
        + where + " ORDER BY u.name", params)

    now_dt = datetime.now()
    results = []
    for s in staff_list:
        sid = s["id"]
        assigned = db.query_all(
            "SELECT c.*, cat.sla_days FROM complaints c "
            "JOIN categories cat ON cat.id = c.category_id "
            "WHERE c.assigned_to = %s", (sid,))

        handled      = len(assigned)
        resolved     = [c for c in assigned if c.get("resolved_at")]
        on_time      = [c for c in resolved
                        if helpers.to_dt(c["resolved_at"]) is not None
                        and helpers.to_dt(c["resolved_at"]) <= helpers.to_dt(c["deadline"])]
        reopen_count = sum(c.get("reopen_count", 0) or 0 for c in assigned)
        open_count   = sum(1 for c in assigned if c["status"] not in config.CLOSED_STATUSES)
        overdue      = sum(1 for c in assigned if helpers.is_breached(c))

        avg_days = None
        if len(resolved) >= 5:  # fewer than 5 = insufficient data
            deltas = []
            for c in resolved:
                assign_event = db.query_one(
                    "SELECT created_at FROM complaint_status_history "
                    "WHERE complaint_id=%s AND new_status='Assigned' "
                    "ORDER BY id ASC LIMIT 1", (c["id"],))
                start = helpers.to_dt(assign_event["created_at"]) if assign_event else helpers.to_dt(c["created_at"])
                end   = helpers.to_dt(c["resolved_at"])
                if start and end:
                    deltas.append((end - start).total_seconds() / 86400.0)
            avg_days = round(sum(deltas) / len(deltas), 1) if deltas else None

        compliance = (round(len(on_time) * 100.0 / len(resolved), 0)
                      if resolved else None)

        ratings = db.query_all(
            "SELECT f.rating FROM feedback f "
            "JOIN complaints c ON c.id = f.complaint_id "
            "WHERE c.assigned_to = %s", (sid,))
        avg_rating   = round(sum(r["rating"] for r in ratings) / len(ratings), 1) if ratings else None
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


@app.route("/admin/performance/<int:staff_id>")
@login_required
@role_required("admin")
def admin_performance_detail(staff_id):
    metrics_list = _staff_metrics(staff_id=staff_id)
    if not metrics_list: abort(404)
    metrics = metrics_list[0]
    member  = db.query_one(
        "SELECT u.*, d.name AS department_name FROM users u "
        "LEFT JOIN departments d ON d.id = u.department_id "
        "WHERE u.id = %s", (staff_id,))

    complaints = db.query_all(
        "SELECT c.*, cat.name AS category_name, cat.priority_weight, "
        "       d.name AS department_name "
        "FROM complaints c "
        "JOIN categories cat      ON cat.id = c.category_id "
        "LEFT JOIN departments d  ON d.id   = c.department_id "
        "WHERE c.assigned_to = %s ORDER BY c.created_at DESC", (staff_id,))
    for c in complaints:
        c["live_score"] = helpers.priority_score(
            c["priority_weight"], c["created_at"], c.get("reopen_count", 0))

    ratings = db.query_all(
        "SELECT f.*, c.ticket_code FROM feedback f "
        "JOIN complaints c ON c.id = f.complaint_id "
        "WHERE c.assigned_to = %s "
        "ORDER BY f.created_at DESC LIMIT 20", (staff_id,))

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
    rows = db.query_all(
        "SELECT status, deadline FROM complaints WHERE user_id = %s",
        (current_user.id,))
    now = helpers.now_str()
    total    = len(rows)
    open_c   = sum(1 for r in rows if r["status"] not in config.CLOSED_STATUSES)
    resolved = sum(1 for r in rows if r["status"] in ("Resolved", "Closed"))
    breached = sum(1 for r in rows
                   if r["status"] not in config.CLOSED_STATUSES
                   and r["deadline"] and r["deadline"] < now)
    return jsonify(total=total, open=open_c, resolved=resolved, breached=breached)


@app.route("/api/live/admin_stats")
@login_required
@role_required("admin")
def api_live_admin_stats():
    """Admin dashboard counters — polled every 20 s by live.js."""
    rows = db.query_all("SELECT status, deadline FROM complaints")
    now  = helpers.now_str()
    all_c       = len(rows)
    pending     = sum(1 for r in rows if r["status"] == "Pending")
    in_progress = sum(1 for r in rows if r["status"] == "In Progress")
    resolved    = sum(1 for r in rows if r["status"] in ("Resolved", "Closed"))
    breached    = sum(1 for r in rows
                      if r["status"] not in config.CLOSED_STATUSES
                      and r["deadline"] and r["deadline"] < now)
    return jsonify(all=all_c, pending=pending, in_progress=in_progress,
                   resolved=resolved, breached=breached)


@app.route("/api/live/staff_stats")
@login_required
@role_required("staff")
def api_live_staff_stats():
    """Staff dashboard counters — polled every 20 s by live.js."""
    rows = db.query_all(
        "SELECT status, deadline FROM complaints WHERE assigned_to = %s",
        (current_user.id,))
    now  = helpers.now_str()
    total    = len(rows)
    open_c   = sum(1 for r in rows if r["status"] not in config.CLOSED_STATUSES)
    resolved = sum(1 for r in rows if r["status"] in ("Resolved", "Closed"))
    breached = sum(1 for r in rows
                   if r["status"] not in config.CLOSED_STATUSES
                   and r["deadline"] and r["deadline"] < now)
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
    user = db.query_one("SELECT * FROM users WHERE id = %s", (current_user.id,))

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

        photo_name = user.get("photo")
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

        db.execute(
            "UPDATE users SET name=%s, phone=%s, program=%s, enrollment_no=%s, "
            "photo=%s, student_department=%s, semester=%s WHERE id=%s",
            (name, phone, program, enrollment_no, photo_name,
             student_department, semester, current_user.id),
        )
        flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("student/profile.html", user=user,
                           programs=CHARUSAT_PROGRAMS,
                           depts=CHARUSAT_STUDENT_DEPTS,
                           semesters=CHARUSAT_SEMESTERS)


if __name__ == "__main__":
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    if config.DB_ENGINE == "sqlite" and not os.path.exists(config.SQLITE_PATH):
        print("Database not found. Run:  python init_db.py")
    app.run(debug=True, host="127.0.0.1", port=5000)
