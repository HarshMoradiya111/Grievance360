"""
Email notification helper for Grievance360.

All public functions accept plain Python values and fire the SMTP send in a
background thread so the calling route is never blocked.

Set MAIL_ENABLED = True in config.py and fill in MAIL_USER / MAIL_PASSWORD to
activate. When MAIL_ENABLED is False every call is a silent no-op — safe for
development.
"""

import logging
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal: send one HTML email in a background thread
# ---------------------------------------------------------------------------
def _send(to_addr, subject, html_body):
    """Low-level send. Called from a daemon thread — never call directly."""
    if not config.MAIL_ENABLED:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.MAIL_FROM
    msg["To"]      = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(config.MAIL_SMTP, config.MAIL_PORT, timeout=10) as s:
            s.ehlo()
            s.starttls()
            s.login(config.MAIL_USER, config.MAIL_PASSWORD)
            s.sendmail(config.MAIL_USER, [to_addr], msg.as_string())
        log.info("Mail sent to %s — %s", to_addr, subject)
    except Exception as exc:
        log.warning("Mail failed to %s: %s", to_addr, exc)


def send_async(to_addr, subject, html_body):
    """Queue an email on a daemon thread and return immediately."""
    t = threading.Thread(target=_send, args=(to_addr, subject, html_body),
                         daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Shared HTML shell
# ---------------------------------------------------------------------------
_ACCENT = "#5b6ea8"
_DARK   = "#33415c"
_BG     = "#f5f6f8"


def _wrap(heading, inner_html, ticket_code=None, action_url=None,
          action_label=None):
    """Wrap content in the branded email shell."""
    action_block = ""
    if action_url and action_label:
        action_block = (
            '<p style="text-align:center;margin:28px 0 0">'
            '<a href="{url}" style="background:{acc};color:#fff;text-decoration:none;'
            'padding:10px 28px;border-radius:6px;font-weight:600;font-size:.9rem">'
            '{label}</a></p>'
        ).format(url=action_url, label=action_label, acc=_ACCENT)

    ticket_line = ""
    if ticket_code:
        ticket_line = (
            '<p style="margin:0 0 16px;font-size:.8rem;color:#64748b">'
            'Ticket&nbsp;<strong style="color:{dk}">{tc}</strong></p>'
        ).format(dk=_DARK, tc=ticket_code)

    return """
<html><body style="margin:0;padding:0;background:{bg};font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"
       style="background:{bg};padding:32px 16px">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#fff;border-radius:10px;overflow:hidden;
                  box-shadow:0 2px 8px rgba(0,0,0,.08)">
      <!-- header -->
      <tr><td style="background:{dk};padding:20px 28px">
        <p style="margin:0;color:#fff;font-size:1.2rem;font-weight:700">
          &#128737; Grievance360</p>
        <p style="margin:4px 0 0;color:rgba(255,255,255,.7);font-size:.78rem">
          CHARUSAT — Student Grievance Portal</p>
      </td></tr>
      <!-- body -->
      <tr><td style="padding:28px 28px 24px">
        <h2 style="margin:0 0 16px;font-size:1.1rem;color:{dk}">{heading}</h2>
        {ticket_line}
        {inner}
        {action}
      </td></tr>
      <!-- footer -->
      <tr><td style="background:{bg};padding:16px 28px;
                     border-top:1px solid #e4e7ec">
        <p style="margin:0;font-size:.75rem;color:#94a3b8;text-align:center">
          Charotar University of Science &amp; Technology (CHARUSAT),
          Changa, Anand, Gujarat &mdash; 388421<br>
          This is an automated message. Do not reply to this email.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>
""".format(bg=_BG, dk=_DARK, heading=heading, ticket_line=ticket_line,
           inner=inner_html, action=action_block)


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------
def notify_complaint_submitted(student_email, student_name, ticket_code,
                                subject, category, deadline, portal_base=None):
    """Confirmation email sent immediately after a complaint is raised."""
    base = portal_base or config.PORTAL_URL
    url  = base + "/complaint/" + ticket_code

    inner = """
<p style="margin:0 0 12px;color:#334155">Dear <strong>{name}</strong>,</p>
<p style="margin:0 0 16px;color:#334155">
  Your complaint has been received and assigned ticket number
  <strong style="color:{acc}">{tc}</strong>.
  Our team will review it and get back to you within the SLA window.
</p>
<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;
       margin-bottom:20px;font-size:.88rem">
  <tr style="background:#eef1f8">
    <td style="padding:8px 12px;color:#64748b;width:40%">Category</td>
    <td style="padding:8px 12px;color:#1e293b">{cat}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#64748b">Subject</td>
    <td style="padding:8px 12px;color:#1e293b">{subj}</td>
  </tr>
  <tr style="background:#eef1f8">
    <td style="padding:8px 12px;color:#64748b">Deadline</td>
    <td style="padding:8px 12px;color:#1e293b">{dl}</td>
  </tr>
</table>
<p style="margin:0;font-size:.85rem;color:#64748b">
  You can track the live status of your complaint at any time using the
  button below.
</p>
""".format(name=student_name, acc=_ACCENT, tc=ticket_code,
           cat=category, subj=subject, dl=deadline)

    html = _wrap(
        "Complaint Received — " + ticket_code,
        inner,
        ticket_code=ticket_code,
        action_url=url,
        action_label="Track My Complaint",
    )
    send_async(student_email,
               "Your complaint " + ticket_code + " has been received — CHARUSAT",
               html)


def notify_status_changed(student_email, student_name, ticket_code,
                           old_status, new_status, remark, portal_base=None):
    """Email every time the complaint status changes."""
    base = portal_base or config.PORTAL_URL
    url  = base + "/complaint/" + ticket_code

    # Pick an emoji indicator for the new status
    icons = {
        "Assigned"   : "&#128203;",
        "In Progress": "&#9881;",
        "Resolved"   : "&#9989;",
        "Closed"     : "&#128274;",
        "Rejected"   : "&#10060;",
        "Reopened"   : "&#128257;",
    }
    icon = icons.get(new_status, "&#128203;")

    status_color = {
        "Resolved" : "#2f6b43",
        "Rejected" : "#991b1b",
        "Closed"   : "#334155",
    }.get(new_status, _ACCENT)

    remark_block = ""
    if remark and remark.strip():
        remark_block = (
            '<div style="background:#f8fafc;border-left:3px solid {acc};'
            'padding:10px 14px;margin:16px 0;border-radius:4px;'
            'font-size:.87rem;color:#334155">'
            '<strong>Remark from staff:</strong><br>{rm}</div>'
        ).format(acc=_ACCENT, rm=remark)

    inner = """
<p style="margin:0 0 14px;color:#334155">Dear <strong>{name}</strong>,</p>
<p style="margin:0 0 16px;color:#334155">
  The status of your complaint has been updated.
</p>
<table cellpadding="0" cellspacing="0"
       style="width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:16px">
  <tr style="background:#eef1f8">
    <td style="padding:8px 12px;color:#64748b;width:40%">Previous status</td>
    <td style="padding:8px 12px;color:#1e293b">{old}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#64748b">New status</td>
    <td style="padding:8px 12px">
      <strong style="color:{sc}">{icon} {new}</strong>
    </td>
  </tr>
</table>
{remark}
<p style="margin:0;font-size:.85rem;color:#64748b">
  Click below to view the full timeline and add comments.
</p>
""".format(name=student_name, old=old_status, new=new_status,
           icon=icon, sc=status_color, remark=remark_block)

    html = _wrap(
        "Status Update — " + ticket_code,
        inner,
        ticket_code=ticket_code,
        action_url=url,
        action_label="View Complaint",
    )
    send_async(student_email,
               "[" + new_status + "] Your complaint " + ticket_code + " — CHARUSAT",
               html)


def notify_comment_added(student_email, student_name, ticket_code,
                          commenter_name, comment_text, portal_base=None):
    """Email when a staff member adds a comment on the student's complaint."""
    base = portal_base or config.PORTAL_URL
    url  = base + "/complaint/" + ticket_code

    inner = """
<p style="margin:0 0 14px;color:#334155">Dear <strong>{name}</strong>,</p>
<p style="margin:0 0 16px;color:#334155">
  <strong>{who}</strong> has added a comment on your complaint.
</p>
<div style="background:#f8fafc;border-left:3px solid {acc};
     padding:12px 16px;border-radius:4px;margin-bottom:20px;
     font-size:.88rem;color:#334155">
  {msg}
</div>
<p style="margin:0;font-size:.85rem;color:#64748b">
  You can reply directly from the complaint page.
</p>
""".format(name=student_name, who=commenter_name,
           acc=_ACCENT, msg=comment_text[:500])

    html = _wrap(
        "New comment on " + ticket_code,
        inner,
        ticket_code=ticket_code,
        action_url=url,
        action_label="View & Reply",
    )
    send_async(student_email,
               "New comment on your complaint " + ticket_code + " — CHARUSAT",
               html)


def notify_complaint_assigned(student_email, student_name, ticket_code,
                               department, assigned_to_name, portal_base=None):
    """Email when the complaint is assigned to a department / staff member."""
    base = portal_base or config.PORTAL_URL
    url  = base + "/complaint/" + ticket_code

    inner = """
<p style="margin:0 0 14px;color:#334155">Dear <strong>{name}</strong>,</p>
<p style="margin:0 0 16px;color:#334155">
  Your complaint has been assigned and is now being reviewed.
</p>
<table cellpadding="0" cellspacing="0"
       style="width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:20px">
  <tr style="background:#eef1f8">
    <td style="padding:8px 12px;color:#64748b;width:40%">Department</td>
    <td style="padding:8px 12px;color:#1e293b">{dept}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#64748b">Assigned to</td>
    <td style="padding:8px 12px;color:#1e293b">{staff}</td>
  </tr>
</table>
<p style="margin:0;font-size:.85rem;color:#64748b">
  You will receive another email when the status changes.
</p>
""".format(name=student_name, dept=department,
           staff=assigned_to_name or "Staff member")

    html = _wrap(
        "Complaint Assigned — " + ticket_code,
        inner,
        ticket_code=ticket_code,
        action_url=url,
        action_label="Track Complaint",
    )
    send_async(student_email,
               "Your complaint " + ticket_code + " has been assigned — CHARUSAT",
               html)


def notify_escalation(admin_email, ticket_code, subject, level_label,
                       student_name, portal_base=None):
    """Alert admins when a complaint is escalated."""
    base = portal_base or config.PORTAL_URL
    url  = base + "/complaint/" + ticket_code

    inner = """
<p style="margin:0 0 14px;color:#334155">
  A complaint has been escalated to <strong style="color:#991b1b">{lvl}</strong>
  level and requires immediate attention.
</p>
<table cellpadding="0" cellspacing="0"
       style="width:100%;border-collapse:collapse;font-size:.88rem;margin-bottom:20px">
  <tr style="background:#fee2e2">
    <td style="padding:8px 12px;color:#64748b;width:40%">Escalation level</td>
    <td style="padding:8px 12px;font-weight:600;color:#991b1b">{lvl}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#64748b">Subject</td>
    <td style="padding:8px 12px;color:#1e293b">{subj}</td>
  </tr>
  <tr style="background:#eef1f8">
    <td style="padding:8px 12px;color:#64748b">Raised by</td>
    <td style="padding:8px 12px;color:#1e293b">{who}</td>
  </tr>
</table>
""".format(lvl=level_label, subj=subject, who=student_name)

    html = _wrap(
        "&#9888; Escalation Alert — " + ticket_code,
        inner,
        ticket_code=ticket_code,
        action_url=url,
        action_label="Review Complaint",
    )
    send_async(admin_email,
               "[ESCALATION] " + ticket_code + " — " + level_label + " — CHARUSAT",
               html)
