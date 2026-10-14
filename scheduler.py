"""
Grievance360 — Automation Background Scheduler.
Runs periodic background sweeps for:
  - Automated SLA Escalations (Level 1, 2, 3)
  - SLA Pre-Breach Early Warnings (75% threshold)
  - Inactive / Stalled Ticket Nudges (48h inactivity)
  - Auto-closure of resolved complaints (Phase 3)
"""

import logging
import os
import sys
import threading
import time

import automation
import config
import db

log = logging.getLogger(__name__)

_scheduler_started = False
_scheduler_lock = threading.Lock()


def _scheduler_loop(app, interval_seconds=1800):
    """Internal loop that runs in a background daemon thread."""
    log.info("Automation scheduler loop started (Interval: %ds)", interval_seconds)
    while True:
        try:
            with app.app_context():
                db_conn = db.get_db()
                log.info("Running scheduled lifecycle automation sweep...")
                result = automation.run_lifecycle_sweep(db_conn)
                log.info("Scheduled sweep completed: %s", result)
        except Exception as exc:
            log.error("Error during scheduled automation sweep: %s", exc)

        time.sleep(interval_seconds)


def start_automation_scheduler(app, interval_seconds=1800):
    """
    Spawns the background scheduler thread if not already running.
    Guarded against Flask development reloader duplicates.
    """
    global _scheduler_started

    # Avoid duplicate threads if Flask reloader is active
    if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
        return

    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

        thread = threading.Thread(
            target=_scheduler_loop,
            args=(app, interval_seconds),
            daemon=True,
            name="Grievance360-AutomationDaemon"
        )
        thread.start()
        log.info("Automation daemon thread launched successfully.")


if __name__ == "__main__":
    # CLI mode for testing or external OS cron jobs
    import app as flask_app
    print("\n--- Running Grievance360 One-Off Automation Sweep ---")
    with flask_app.app.app_context():
        db_conn = db.get_db()
        res = automation.run_lifecycle_sweep(db_conn)
        print("Sweep Result:", res)
