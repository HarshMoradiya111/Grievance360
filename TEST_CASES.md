# Grievance360 — Test Cases

All 60 cases below were executed against the running application on
**17 Aug 2026** using an automated HTTP smoke test that drives the real routes
with real sessions. Result: **60 / 60 passed**.

Re-run them any time the code changes, and update the "Actual" column if a
result differs.

---

## 1. Public pages

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 1 | Landing page loads | GET `/` | 200, hero + stat tiles | As expected | Pass |
| 2 | Login page loads | GET `/login` | 200, login form | As expected | Pass |
| 3 | Register page loads | GET `/register` | 200, registration form | As expected | Pass |
| 4 | Forgot-password page loads | GET `/forgot` | 200, email form | As expected | Pass |

## 2. Access control — not logged in

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 5 | Student area is protected | GET `/student` | Redirect to `/login` | As expected | Pass |
| 6 | Staff area is protected | GET `/staff` | Redirect to `/login` | As expected | Pass |
| 7 | Admin area is protected | GET `/admin` | Redirect to `/login` | As expected | Pass |
| 8 | Analytics is protected | GET `/admin/analytics` | Redirect to `/login` | As expected | Pass |

## 3. Authentication

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 9 | Student login + role redirect | `harsh@student.edu` / `student123` | Lands on `/student` | As expected | Pass |
| 10 | Student dashboard renders | — | Complaint cards + stat tiles | As expected | Pass |
| 11 | Admin login + role redirect | `admin@grievance360.edu` / `admin123` | Lands on `/admin` | As expected | Pass |
| 12 | Staff login + role redirect | `it.staff@grievance360.edu` / `staff123` | Lands on `/staff` | As expected | Pass |

## 4. Role-based access control

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 13 | Student blocked from admin | Student opens `/admin` | Redirected away + error flash | As expected | Pass |
| 14 | Student blocked from staff | Student opens `/staff` | Redirected away | As expected | Pass |
| 15 | Student blocked from analytics | Student opens `/admin/analytics` | Redirected away | As expected | Pass |
| 16 | Student blocked from complaint list | Student opens `/admin/complaints` | Redirected away | As expected | Pass |

## 5. Raise a complaint

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 17 | Raise form loads | GET `/complaint/new` | 200, form with category dropdown | As expected | Pass |
| 18 | Categories are populated | — | 6 categories, each with an SLA | As expected | Pass |
| 19 | Complaint is created | Valid category + subject + description | Ticket code `GRV-2026-####` generated | `GRV-2026-0031` | Pass |
| 20 | Redirect to track page | — | Lands on `/complaint/<ticket>` | As expected | Pass |
| 21 | First history row written | — | Timeline shows "Complaint submitted by student" | As expected | Pass |

## 6. JSON status API

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 22 | API returns current status | GET `/api/complaint/<code>/status` | `{"status": "Pending", ...}` | As expected | Pass |
| 23 | API returns SLA deadline | — | Non-empty formatted deadline | As expected | Pass |
| 24 | API history count | — | `history_count = 1` on a new complaint | As expected | Pass |

## 7. Notifications

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 25 | Notification API responds | GET `/api/notifications` | 200 with `unread` + `items` | As expected | Pass |

## 8. Admin dashboard & auto-routing

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 26 | Priority queue renders | GET `/admin` | Queue sorted by priority score | As expected | Pass |
| 27 | SLA breach panel renders | — | Red list of overdue complaints | As expected | Pass |
| 28 | Admin search finds a complaint | `?q=Smoke test` | Matching ticket shown | As expected | Pass |
| 29 | Assign page loads | GET `/complaint/<id>/assign` | 200 with staff dropdown | As expected | Pass |
| 30 | **Auto-routing suggests correctly** | Description mentions "wifi", "printer", "lab" | Suggests **IT Support** | Suggested IT Support | Pass |
| 31 | Staff list populated with workload | — | 4 staff, each with open count | As expected | Pass |

## 9. Assignment

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 32 | Assign to staff succeeds | Pick IT staff + remark | Redirect, success flash | As expected | Pass |
| 33 | Status becomes Assigned | — | API reports `Assigned` | As expected | Pass |

## 10. Staff workflow

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 34 | Staff dashboard loads | GET `/staff` | Complaints assigned to this staff member | As expected | Pass |
| 35 | Assigned ticket is visible | — | New ticket appears in the list | As expected | Pass |
| 36 | Status form loads | GET `/complaint/<id>/status` | 200 with status dropdown | As expected | Pass |
| 37 | Status → In Progress | Status + remark | Updated, logged in history | As expected | Pass |
| 38 | Status → Resolved | Status + remark | Updated, `resolved_at` set | As expected | Pass |

## 11. Feedback & reopen

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 39 | Rating form appears only when resolved | Student opens a Resolved ticket | Star widget shown | As expected | Pass |
| 40 | Feedback is accepted | 4 stars + remark | Thank-you flash, row in `feedback` | As expected | Pass |
| 41 | Rating auto-closes the ticket | — | Status becomes `Closed` | As expected | Pass |
| 42 | Reopen works | Reason text | Status becomes `Reopened` | As expected | Pass |
| 43 | Reopen restarts the SLA clock | — | New deadline, `reopen_count` = 1 | As expected | Pass |

## 12. Comments

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 44 | Comment is posted | Message text | Appears in the conversation thread | As expected | Pass |

## 13. Data isolation

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 45 | **Another student cannot view the ticket** | Priya opens Harsh's ticket | Blocked + redirected | As expected | Pass |

## 14. Analytics, filters, exports

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 46 | Analytics page loads | GET `/admin/analytics` | 200 | As expected | Pass |
| 47 | Chart data block present | — | `analyticsData` JSON block rendered | As expected | Pass |
| 48 | Avg resolution time per dept | — | Table with days + count per department | As expected | Pass |
| 49 | Top recurring issue shown | — | Highlight banner with the largest category | As expected | Pass |
| 50 | SLA breach report present | — | Red table of overdue complaints | As expected | Pass |
| 51 | Status filter | `?status=Pending` | Only Pending rows | As expected | Pass |
| 52 | SLA-breached filter | `?breached=1` | Only overdue open rows | As expected | Pass |
| 53 | Pagination | `?page=2` | Second page of 20 | As expected | Pass |
| 54 | Excel export | GET `/admin/export/excel` | Valid `.xlsx` download | Valid ZIP/xlsx, >3 KB | Pass |
| 55 | PDF print view | GET `/admin/export/pdf` | Print-optimized report page | As expected | Pass |

## 15. Password reset

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 56 | Reset token generated | Registered email | One-time link shown, valid 1 hour | As expected | Pass |
| 57 | Password is updated | New password twice | Success + redirect to login | As expected | Pass |
| 58 | Login with new password | New credentials | Lands on `/student` | As expected | Pass |

## 16. Error handling & validation

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| 59 | Unknown ticket code | `/complaint/GRV-9999-9999` | Custom 404 page | As expected | Pass |
| 60 | Short input rejected | 2-char subject, 5-char description | Validation errors, no row inserted | As expected | Pass |

---

## Additional manual checks (do these before the viva)

| # | Test case | Expected |
|---|---|---|
| M1 | File upload — attach a JPG under 5 MB | Saved to `static/uploads`, link on track page |
| M2 | File upload — attach a `.exe` | Rejected with "Only these file types are allowed" |
| M3 | File upload — attach a file over 5 MB | Rejected with the size error |
| M4 | Anonymous complaint | Staff sees "Anonymous" instead of the student's name |
| M5 | Live polling | Change status as staff; the student's open track page updates without a refresh |
| M6 | Notification bell | Unread badge appears within 15 seconds of a status change |
| M7 | Duplicate email registration | "That email is already registered" |
| M8 | Mismatched passwords on registration | "The two passwords do not match" |
| M9 | 360px mobile view | No horizontal scroll, tables become cards, bottom nav visible |
| M10 | 1440px desktop view | Content centred, tables shown, no stretched layout |
