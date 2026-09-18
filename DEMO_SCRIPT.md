# Grievance360 — Viva Demo Script

A rehearsed click-path showing the complete lifecycle in about **7 minutes**.
Practise it end to end at least twice.

---

## Before you start

```bash
python init_db.py
```

```bash
python database/sample_data.py
```

```bash
python app.py
```

- [ ] Open **three browser windows**, logged in as student / admin / staff, so
      you never waste time logging in and out on stage
- [ ] Put the **student window in mobile view** — DevTools (F12) → device
      toolbar → 360px. This is your responsiveness proof, always on screen
- [ ] Keep the admin window on desktop width for the charts
- [ ] Have `helpers.py` open in your editor for the formula questions

---

## Act 1 — The student raises a complaint · 90s

> *"98% of our users are students on phones, so I'll demo the student side at
> 360px — the real screen size."*

- [ ] **[MOBILE]** Show the student dashboard — complaints render as **cards**,
      one per row, colour-coded status badges, no horizontal scrolling
- [ ] Tap the **bottom navigation bar** → *Raise*
      → *"Bottom nav, because a phone is used with one thumb."*
- [ ] Fill the form:
  - Category: **Internet & Computer Lab**
  - Point out the hint that updates: *"resolved within 2 day(s)"* — the SLA
  - Subject: `WiFi and printer dead in computer lab 3`
  - Description: `The wifi keeps disconnecting and the printer in computer lab 3 shows a paper jam error. Nobody can submit practicals.`
  - Attach a photo (optional)
  - Leave *anonymous* unchecked — mention it exists
- [ ] Submit → **read the ticket number aloud**: `GRV-2026-####`
- [ ] Land on the track page → timeline shows **Pending**

**📱 RESPONSIVENESS MOMENT:** everything so far has been at 360px.

---

## Act 2 — Auto-routing and assignment · 90s

- [ ] Switch to the **admin window**
- [ ] Dashboard: point at the **stat tiles**, then the **priority queue**
      → *"Sorted by our priority score, not by date."*
- [ ] Point at the **SLA breach panel** — the red list
- [ ] Go to **All Complaints** → search the new ticket → click **Assign**

**⭐ THE MOMENT TO LAND:**

> *"The system read the description, matched the words 'wifi', 'printer' and
> 'lab' against each department's keyword map, weighted subject hits three
> times heavier than body hits, and suggested IT Support automatically. The
> admin still has the final say."*

- [ ] Show the blue **"Auto-routing suggests: IT Support"** banner
- [ ] Open the staff dropdown → point out the **open-complaint count** next to
      each name → *"so we don't overload one person"*
- [ ] Assign to **Neha Shah**, add a remark, submit

---

## Act 3 — Live updates without a refresh · 60s

**⭐ THE SECOND MOMENT TO LAND:**

- [ ] Bring the **student mobile window** back on screen, on the track page
      → *"I have not touched this window. Watch the badge."*
- [ ] In the **staff window**: open the complaint → *Update status* →
      **In Progress** → remark `Router restarted, monitoring the lab.` → Save
- [ ] Within 5 seconds the **student's badge changes on its own**
      → *"fetch() polls a JSON API every 5 seconds — no page reload."*
- [ ] Point at the **notification bell** — unread count appears

---

## Act 4 — Resolution, rating, reopen · 90s

- [ ] **[STAFF]** Update status → **Resolved** → remark
      `Replaced the access point and cleared the printer jam.`
- [ ] **[STUDENT, MOBILE]** The timeline now shows the full journey, and a
      **star rating widget** has appeared
      → *"The rating form only exists once the complaint is resolved."*
- [ ] Give **4 stars** + a remark → submit → status becomes **Closed**
- [ ] Scroll down → show the **Reopen** button
      → *"If the problem comes back, one tap reopens it, restarts the SLA
      clock, and adds 5 points to the priority score."*
- [ ] Optionally reopen it to show the status flip to **Reopened**

---

## Act 5 — Analytics and reports · 90s

- [ ] **[ADMIN, DESKTOP]** Open **Analytics**
- [ ] Walk the four charts: status doughnut, category bar, department bar,
      monthly trend line
- [ ] Point at the **Top recurring issue** banner
      → *"The single largest source of grievances — fix the root cause here
      and you remove the most tickets."*
- [ ] Show **average resolution time per department**
      → *"Computed from the status history table, from created_at to
      resolved_at."*
- [ ] Show the **SLA breach report** — the red table
- [ ] Go back to **All Complaints** → apply a filter → click **Excel**
      → the file downloads with exactly the filtered rows
- [ ] Click **PDF** → print-optimized report opens

---

## Act 6 — The closing point · 30s

- [ ] Shrink the **admin window** to 360px live, in front of them
- [ ] The wide table **becomes stacked cards**, the filters **collapse into an
      accordion**, the bottom nav appears
      → *"Same page, same route, no separate mobile site. One base.html owns
      all responsiveness and every page inherits it."*

---

## Likely examiner questions — prepared answers

**"How does the priority score work?"**
> `(priority_weight × 10) + (days_since_created × 2) + (reopen_count × 5)`.
> It's in `helpers.priority_score()`. The age term is the important one — it
> keeps growing, so an old low-priority complaint eventually overtakes a fresh
> high-priority one. Nothing can sit forgotten forever.

**"How do you detect an SLA breach?"**
> `deadline` is set at submission as `created_at + category.sla_days`. A
> complaint is breached if the status is not Resolved, Closed or Rejected and
> the deadline has passed. `helpers.is_breached()`.

**"Is it secure against SQL injection?"**
> Every query is parameterized — including the dynamic admin filters. In
> `_build_where()` the WHERE clause is built from fixed strings and every value
> goes in as a separate parameter, so user input is never part of the SQL text.

**"How are passwords stored?"**
> Hashed with Werkzeug's `generate_password_hash`. The database never holds a
> plain password — that's why seed accounts are created in `init_db.py` rather
> than pasted into `schema.sql`.

**"Why SQLite instead of MySQL?"**
> The design is MySQL-first — `database/schema.sql` is the canonical schema and
> every query uses MySQL's `%s` placeholders. `db.py` has a four-line shim that
> rewrites `%s` to `?` for SQLite, so the project runs anywhere with no server
> install. Switching to MySQL is one line in `config.py` and not a single query
> changes.

**"What happens if two students upload `photo.jpg`?"**
> Uploads get a random hex prefix, so they can never overwrite each other.
> There's also an extension allow-list and a 5 MB cap.

**"Can a student see someone else's complaint?"**
> No. `can_view()` checks ownership on every complaint route — students see
> only their own, staff see only what's assigned to them or routed to their
> department, admins see everything.

**"Why poll instead of using WebSockets?"**
> Polling with `fetch()` is simple, needs no extra server, and works through
> any college firewall. At 5-second intervals on a read-only indexed query the
> load is negligible for this scale.

---

## Emergency recovery

| If this happens | Do this |
|---|---|
| Data looks wrong or messy | `python init_db.py` then `python database/sample_data.py` |
| Port 5000 already in use | Change the port on the last line of `app.py` |
| Charts don't render | Check internet — Chart.js loads from CDN |
| A page errors out | Show the custom error page, then use a different ticket |
