"""
Seed common and useful Knowledge Base articles in MongoDB for Grievance360 Help Centre.
"""

import os
import sys
from datetime import datetime, timedelta

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import config
import db
import helpers

def seed_articles():
    db_conn = db._connect()
    
    # 1. Fetch categories
    cats = {c["name"]: c["_id"] for c in db_conn.categories.find()}
    print(f"Found {len(cats)} categories in database: {list(cats.keys())}")
    
    # 2. Fetch admin user
    admin = db_conn.users.find_one({"role": "admin"})
    admin_id = admin["_id"] if admin else None
    print(f"Using Admin ID: {admin_id}")
    
    # Base timestamp
    now = datetime.now()
    
    ARTICLES_DATA = [
        # --- Internet & Computer Lab ---
        {
            "title": "How do I connect to the Campus Wi-Fi and register my device?",
            "category_name": "Internet & Computer Lab",
            "views": 68,
            "helpful_yes": 42,
            "helpful_no": 1,
            "deflections": 18,
            "days_ago": 25,
            "body": """Connecting your laptop, tablet, or smartphone to the high-speed campus wireless network:

1. Network Connection Details:
   • Network SSID: CHARUSAT-Student (or Campus-Student-WiFi)
   • Security Type: WPA2-Enterprise / Captive Portal Web Authentication
   • Supported Bands: 2.4 GHz and 5 GHz (802.11ac / Wi-Fi 6 supported)

2. Step-by-Step Login Instructions:
   • Turn on Wi-Fi on your device and select "CHARUSAT-Student".
   • A captive portal login window should pop up automatically. If it does not, open any web browser (Chrome/Edge/Safari) and browse to http://10.0.0.1 or http://captive.apple.com.
   • Username: Enter your Student Enrollment Number (e.g., MSCIT2026001).
   • Password: Enter your centralized Student Portal password.
   • Accept the Campus Acceptable Use Policy and click "Log In".

3. MAC Address Registration for Hostels & Specialized Labs:
   • In university hostel blocks and computational labs, network security enforces hardware MAC filtering.
   • IMPORTANT: iOS and Android devices enable "Private Wi-Fi Address" (MAC Randomization) by default. To stay authenticated, go to your phone's Wi-Fi settings for CHARUSAT-Student and switch "Private MAC Address" to "Off" or "Device MAC".
   • If you change your laptop or smartphone, submit your new Wi-Fi MAC address at the IT Support Helpdesk or update it in your Student Profile.

4. Troubleshooting Common Wi-Fi Issues:
   • "Authentication Failed" error: Verify your credentials on the student portal. If you recently changed your password, "Forget" the Wi-Fi network and reconnect.
   • "Connected without Internet" error: Ensure your student account is in active status and you have not exceeded your semester bandwidth quota.
   • For signal dead spots in academic blocks or hostel corridors, raise a complaint under the "Internet & Computer Lab" category specifying your building, wing, and room number.
   • IT Helpdesk Location: Room 105, Central IT Block (Open Mon–Sat, 9:00 AM – 5:30 PM, Ext. 105)."""
        },
        {
            "title": "How do I reset my student portal or institutional email password?",
            "category_name": "Internet & Computer Lab",
            "views": 54,
            "helpful_yes": 38,
            "helpful_no": 0,
            "deflections": 21,
            "days_ago": 22,
            "body": """Self-service recovery and helpdesk procedures if you are unable to access your student portal, Wi-Fi, or college email account:

1. Self-Service Portal Password Reset (Fastest Method):
   • Navigate to the Student Login page and click on "Forgot Password?".
   • Enter your Student Enrollment Number and the secondary personal email address registered during admission.
   • A secure 6-digit OTP and reset link will be dispatched immediately to your email and SMS.
   • Reset links expire after 15 minutes for security.
   • Create a strong password containing at least 8 characters with uppercase letters, numbers, and symbols.

2. Institutional Google / Microsoft 365 Email Accounts:
   • Your official college email (e.g., enrollment@student.edu) provides access to Google Classroom, Microsoft Teams, library journals, and academic notices.
   • If you lose your Two-Factor Authentication (2FA) device or phone authenticator, the institutional admin must generate backup recovery codes.
   • Email a request from your alternate personal email to itsupport@college.edu quoting your Enrollment ID, Department, and attaching a photo of your Student ID card.

3. In-Person Identity Verification (If Contact Info Has Changed):
   • If you no longer have access to the mobile number or secondary email registered with the university:
   • Visit the IT Support Cell (Room 105, Central Building) in person.
   • Present your original physical University ID Card or Government Photo ID (Aadhaar / Driving License / Passport).
   • For student security and fraud prevention, phone or third-party requests to change login contact info are strictly prohibited."""
        },
        {
            "title": "What should I do if lab computer systems, software licenses, or printers are malfunctioning?",
            "category_name": "Internet & Computer Lab",
            "views": 41,
            "helpful_yes": 26,
            "helpful_no": 2,
            "deflections": 9,
            "days_ago": 18,
            "body": """Guidelines for reporting lab workstation faults, software errors, or network printing issues:

1. Immediate In-Lab Reporting:
   • If a computer freezes, fails to boot, or exhibits blue-screen errors during practical sessions, inform the Lab Attendant or Faculty In-Charge immediately.
   • Do not attempt to open CPU casings, switch power cables, or tamper with networking patch panels.

2. Software Licenses & IDE Crashes:
   • Standard lab installations (MATLAB, Oracle DB, IntelliJ, AutoCAD, VS Code, Python SDKs) are managed centrally.
   • If a license key expired prompt appears on specialized engineering or design software, report the workstation ID to the lab assistant so the IT license server can re-sync tokens.

3. Campus Printing & Scanning Service:
   • Centralized student printing stations are available in the Central Library and Computer Lab 2.
   • If the printer shows paper jam, toner low, or spooler errors, inform the library circulation counter. Avoid pulling jammed sheets manually.

4. Logging a Formal Repair Ticket:
   • If an entire lab cluster has connectivity drops or a workstation remains dysfunctional across multiple lab hours:
   • Raise a ticket under "Internet & Computer Lab" on Grievance360.
   • Provide the specific Lab Number (e.g. Lab 4, Block C, 3rd Floor) and the Workstation Number (e.g. WS-24).
   • SLA Turnaround: Hardware and software faults in teaching labs are inspected within 4 hours and resolved within 24 hours."""
        },

        # --- Examination & Results ---
        {
            "title": "How do I apply for rechecking or revaluation of my exam papers?",
            "category_name": "Examination & Results",
            "views": 89,
            "helpful_yes": 62,
            "helpful_no": 2,
            "deflections": 34,
            "days_ago": 28,
            "body": """Official university regulations and procedure for applying for re-evaluation, verification, or re-totaling of end-semester examination answer scripts:

1. Time Limit & Eligibility:
   • The revaluation window opens immediately after online result publication and remains open for exactly 10 calendar days.
   • Late applications are rejected automatically by the Examination Management System.
   • Revaluation is permitted for theory subjects only; practicals, term work, viva-voce, and internal continuous assessments are not eligible.

2. Fee Structure:
   • Re-totaling / Verification of Marks: ₹100 per course/subject.
   • Revaluation (Complete reassessment by external evaluator): ₹150 per course/subject.
   • Photocopy of Evaluated Answer Sheet: ₹200 per subject.

3. Application Procedure:
   • Step 1: Download the Revaluation Application Form from the student portal or collect a printed copy from the Examination Section (Room 101).
   • Step 2: Pay the requisite fee online via the Student Fee Portal or at the Accounts Cash Counter (Building A, Ground Floor). Keep the transaction receipt.
   • Step 3: Attach the self-attested internet result copy and payment receipt with the form.
   • Step 4: Submit the complete dossier at the Examination Section counter and obtain a stamped acknowledgement slip.

4. Evaluation Criteria & Outcome:
   • A subject expert other than the original examiner evaluates the masked answer script.
   • If the new score differs by 10% or more from the original total, the revised score is awarded as final.
   • In case of a change in marks, an updated Grade Card is issued free of cost upon surrendering the old one.
   • Timeline: Revaluation outcomes are declared within 30 to 45 working days."""
        },
        {
            "title": "What should I do if my exam hall ticket has an error or is not downloading?",
            "category_name": "Examination & Results",
            "views": 63,
            "helpful_yes": 45,
            "helpful_no": 1,
            "deflections": 17,
            "days_ago": 20,
            "body": """Instructions for troubleshooting Hall Ticket / Admit Card download issues and rectifying clerical discrepancies:

1. When are Hall Tickets Released?
   • Hall tickets are typically published for download on the student portal 5 to 7 days prior to the commencement of end-semester examinations.
   • You must download, print two hard copies, and carry one along with your physical College ID Card to every exam session.

2. Common Reasons Why Hall Ticket Download is Blocked:
   • Attendance Shortage: If your cumulative attendance in any subject is below the mandatory university threshold (75%), your hall ticket may be held pending condonation review by the Head of Department.
   • Outstanding Dues: Pending semester tuition fees, hostel rent, or library overdue fines will temporarily prevent hall ticket generation. Clear pending dues with Accounts and allow up to 6 hours for automatic system clearance.
   • Unapproved Exam Registration Form: Ensure you submitted the semester exam registration form during the enrollment window.

3. Correcting Clerical Errors (Name, Photograph, or Course Codes):
   • If your hall ticket displays a misspelled name, missing subject code, or incorrect photograph:
   • Immediately visit the Controller of Examinations (CoE) Office (Room 102, Administrative Block).
   • Carry: Government Photo ID (Aadhaar / Passport), Admission Slip, and 2 passport-size photographs.
   • Corrections must be submitted at least 48 hours prior to the first examination date.
   • For urgent assistance on exam day, report to the Chief Exam Superintendent at the Central Control Room 45 minutes before paper start time."""
        },
        {
            "title": "How do I request an official transcript, bonafide, or leaving certificate?",
            "category_name": "Examination & Results",
            "views": 72,
            "helpful_yes": 51,
            "helpful_no": 1,
            "deflections": 25,
            "days_ago": 24,
            "body": """Step-by-step procedure for obtaining institutional documentation for higher education, visa processing, job verifications, or transfers:

1. Bonafide / Study Certificate:
   • Needed for: Educational loans, state bus/train transit passes, visa applications, scholarship forms.
   • Application: Apply through the Student Portal under "Document Requests" or submit a written request at the Administrative Office (Window 3).
   • Fee: Free of charge for active students.
   • Processing Time: Ready within 24 to 48 business hours.

2. Official Academic Transcripts (Sealed / Attested):
   • Needed for: Higher studies abroad (WES, credential evaluators, university admissions).
   • Required Documents: Photocopies of all semester grade cards, Degree/Provisional Certificate (for alumni), and Government ID.
   • Application Fee: ₹500 for the first 3 sets, ₹100 for each additional set.
   • Sealed Envelope: Transcripts are embossed with the Registrar's seal and signed across envelope flaps for official international courier dispatch.
   • Processing Time: 7 to 10 working days.

3. College Leaving / Transfer / Migration Certificate:
   • Mandatory No-Dues Clearance:
     - Central Library (clear all borrowed books and fines).
     - Department Laboratory In-charge (return issued kits/components).
     - Hostel Warden (hand over room keys and clearance slip).
     - Finance & Accounts Section (zero balance verification).
   • Submit the consolidated No-Dues form at the Registrar’s Office.
   • Processing Time: 5 to 7 working days. You will receive an SMS and email notification when documents are ready for counter collection."""
        },

        # --- Infrastructure & Maintenance ---
        {
            "title": "How do I report broken classroom furniture, AC/fan failures, or electrical faults?",
            "category_name": "Infrastructure & Maintenance",
            "views": 49,
            "helpful_yes": 33,
            "helpful_no": 1,
            "deflections": 14,
            "days_ago": 21,
            "body": """How to submit and track repairs for classroom infrastructure and lecture hall amenities:

1. What Information is Required in Your Ticket?
   • Building Name & Block (e.g., Engineering Block B, Science Complex).
   • Floor & Classroom/Lab Number (e.g., 2nd Floor, Room 204).
   • Specific Asset & Problem Description (e.g., "Middle row wooden bench joint broken", "Ceiling fan speed regulator unresponsive", "Air conditioning unit leaking water").
   • Photo attachment (optional but highly recommended) — helps the maintenance supervisor dispatch the correct carpenter, electrician, or technician with the right replacement parts.

2. Standard Maintenance Turnaround Times (SLAs):
   • Classroom Fans & Tube Lights: Replaced within 24 hours.
   • Air Conditioning & Ventilation Servicing: Repaired within 2 to 3 business days.
   • Furniture & Desk Repairs: Repaired within 3 to 5 business days.
   • Smart Board / Audio-Visual Cabling: Attended to same day if reported before 2:00 PM.

3. Urgent During-Class Assistance:
   • If a failure occurs right before a scheduled lecture or lab exam, call the Floor Attendant or dial Ext. 2100 on the corridor intercom for immediate standby replacement."""
        },
        {
            "title": "Who do I contact for emergency electrical, plumbing, or water leakage issues?",
            "category_name": "Infrastructure & Maintenance",
            "views": 58,
            "helpful_yes": 44,
            "helpful_no": 0,
            "deflections": 19,
            "days_ago": 26,
            "body": """Crucial protocols and emergency contacts for hazardous campus maintenance incidents:

1. Emergency Scenarios Requiring Instant Action:
   • Electrical sparking, burning wire smell, or short circuits in classrooms, labs, or hostels.
   • Major pipe bursts causing water flooding near electrical switchboards or walkways.
   • Structural hazards, shattered window panes, or jammed fire escape doors.
   • People trapped inside campus passenger elevators.

2. Immediate 24/7 Campus Control Room Hotlines:
   • Campus Maintenance Control Room: Dial Ext. 2200 (from any internal campus phone) or Call +91-2697-265000 / 265001.
   • Fire & Safety Officer: Ext. 2299.
   • Security Main Gate Guard: Ext. 1000.
   • Lift Emergency Rescue: Look for the emergency yellow button inside the elevator cab or call the number displayed on the elevator control panel.

3. Critical Safety Precautions:
   • Never touch wet switches or step into pooled water near live electrical conduits.
   • Keep students and visitors at least 15 feet away from the affected area.
   • If you know the location of the local Miniature Circuit Breaker (MCB) and can safely reach it without entering wet areas, trip the breaker.
   • File an Emergency Complaint on Grievance360 so safety teams receive automated priority dispatch."""
        },

        # --- Cleanliness & Hygiene ---
        {
            "title": "What is the campus cleaning schedule and how do I report unhygienic washrooms?",
            "category_name": "Cleanliness & Hygiene",
            "views": 46,
            "helpful_yes": 32,
            "helpful_no": 1,
            "deflections": 12,
            "days_ago": 19,
            "body": """Housekeeping routines and procedures for keeping university washrooms, corridors, and public areas clean:

1. Campus Housekeeping Shifts:
   • Shift 1 (Morning Deep Clean): 7:00 AM – 8:45 AM (All washrooms disinfected, floors mopped, soap dispensers filled, and trash emptied before classes start).
   • Shift 2 (Midday Touch-up): 1:00 PM – 2:30 PM (Sanitizing high-traffic restrooms, refilling liquid soap, and clearing canteen trash cans).
   • Shift 3 (Evening Mop-down): 5:00 PM – 6:30 PM (Full sweep and chemical floor scrub across all department corridors).

2. How to Report Washroom & Corridor Cleanliness Issues:
   • Submit a grievance under "Cleanliness & Hygiene".
   • Include: Building Block, Floor level, Wing (East/West), and specific Restroom (e.g. "Block C, 3rd Floor, West Wing Men's Restroom").
   • Mention what is missing or defective: e.g., soap dispenser empty, tap leaking, dustbin overflowing, or water shortage.

3. SLA Deadlines:
   • Washroom soap replenishment and trash bin emptying: Attended to within 2 to 3 hours during working hours.
   • Deep sanitation or blocked drainage: Resolved within 24 hours.
   • Campus Sanitary Napkin Vending Machines & Incinerators: For refills or coin/token malfunctions in women's restrooms, report with machine number for same-day replenishment."""
        },

        # --- Hostel & Canteen ---
        {
            "title": "What is the policy for reporting hostel mess food quality and canteen hygiene?",
            "category_name": "Hostel & Canteen",
            "views": 76,
            "helpful_yes": 56,
            "helpful_no": 2,
            "deflections": 28,
            "days_ago": 27,
            "body": """Standards, inspection procedures, and complaint redressal for university hostel messes and campus food courts:

1. Food Quality & Safety Standards:
   • All hostel mess contractors and canteen vendors must strictly comply with FSSAI regulations and university nutrition guidelines.
   • The Student Mess Committee and Faculty Wardens conduct unannounced inspections weekly to inspect raw ingredient quality, oil freshness, refrigeration hygiene, and water purity.
   • Drinking water delivered through water coolers undergoes laboratory bacteriological testing every 30 days.

2. When and How to Report Substandard Food:
   • If you observe stale food, foreign objects, undercooked dishes, unhygienic handling by kitchen staff, or overcharging beyond the approved university canteen menu rates:
   • Step 1: Notify the Student Mess Committee representative or the Hostel Assistant Warden immediately so an on-the-spot sample can be inspected.
   • Step 2: File a ticket on Grievance360 under "Hostel & Canteen" detailing the meal date, session (Breakfast/Lunch/Dinner), and exact issue. Attach photos if applicable.

3. Contractual Penalties & Escalation:
   • First valid offense: Formal warning and monetary fine levied against the caterer.
   • Repeated offenses: Immediate forfeiture of security deposit and termination of the catering contract.
   • Health Emergencies: If you experience acute gastrointestinal symptoms or suspect food poisoning, visit the 24/7 University Health Centre (SAC Ground Floor, Ext. 1108) immediately."""
        },
        {
            "title": "How do I request hostel room repairs, geyser servicing, or water cooler maintenance?",
            "category_name": "Hostel & Canteen",
            "views": 59,
            "helpful_yes": 41,
            "helpful_no": 1,
            "deflections": 16,
            "days_ago": 23,
            "body": """Guidelines for residential students to request prompt maintenance for hostel amenities:

1. Common Hostel Maintenance Items:
   • Electrical: Fused LED tube lights, ceiling fan speed regulators, power sockets.
   • Plumbing: Dripping taps, clogged shower drains, low water pressure, flush tank leaks.
   • Appliances: Winter geysers/solar hot water heaters, RO drinking water purifiers, corridor water coolers.
   • Carpentry: Door locks, cupboard latches, study table repairs, window insect mesh.

2. How to Log a Repair Request:
   • Method 1: Raise a ticket on Grievance360 under "Hostel & Canteen" specifying Hostel Block Name (e.g., Hostel Block 2), Floor, and Room Number.
   • Method 2: Log your room number and problem in the Hostel Maintenance Register maintained at the Warden's Desk.

3. Resolution SLA & In-Room Access:
   • RO drinking water purifiers & water coolers: Priority repair within 12 to 24 hours.
   • Geyser heating faults & electrical issues: Repaired within 24 hours.
   • Carpentry and paint touch-ups: Completed within 48 to 72 hours.
   • Safety Protocol: Maintenance staff are accompanied by the hostel warden or floor supervisor. Technicians will not enter student rooms without staff presence."""
        },
        {
            "title": "How do I apply for hostel night-out, leave permissions, or room changes?",
            "category_name": "Hostel & Canteen",
            "views": 61,
            "helpful_yes": 43,
            "helpful_no": 1,
            "deflections": 22,
            "days_ago": 20,
            "body": """Official hostel regulations regarding night-out passes, weekend leave, and room allocations:

1. Digital Leave / Gate Pass Application:
   • Applications for night-out or home visit leaves must be submitted via the Student Portal at least 24 hours prior to planned departure.
   • An automated OTP confirmation or approval email is dispatched to your registered parent/guardian’s mobile number.
   • Once parental approval and Warden authorization are logged, a digital QR Gate Pass is generated on your mobile screen to be scanned at the main campus security gate.

2. Curfew Timings & Entry Regulations:
   • Normal hostel entry cutoff: 8:30 PM on weekdays (Monday through Friday) and 9:30 PM on weekends and public holidays.
   • Students participating in sanctioned university labs, library night sessions, or hackathons must obtain a stamped Extended Hours Permit endorsed by their Faculty Guide.

3. Hostel Room Change Requests:
   • Room reallocation requests are accepted exclusively during the first two weeks of each new academic semester.
   • Mutual Room Swap: If two students wish to exchange rooms, both must fill out the Mutual Transfer Form and obtain consent from their respective Block Wardens.
   • Single room allotment requests based on medical conditions require certification from the University Medical Officer."""
        },

        # --- Library & Study Material ---
        {
            "title": "What are the library book borrowing limits, renewal rules, and fine policies?",
            "category_name": "Library & Study Material",
            "views": 52,
            "helpful_yes": 37,
            "helpful_no": 0,
            "deflections": 15,
            "days_ago": 17,
            "body": """Everything you need to know about borrowing books, digital catalog searches, and library regulations:

1. Book Borrowing Entitlements:
   • Undergraduate Students: Up to 3 books for 14 calendar days.
   • Postgraduate Students: Up to 5 books for 21 calendar days.
   • Research Scholars & PhDs: Up to 8 books for 30 calendar days.
   • Reference Section materials, current journals, dictionaries, and rare manuscripts cannot be checked out and must be consulted inside the reading hall.

2. Online Renewals & Book Reservations:
   • Books may be renewed once for an additional 7 days through the Web OPAC (Online Public Access Catalog) or at the circulation counter, provided no other student has placed a reservation/hold on the title.
   • Renewals must be completed on or before the due date stamped on the book slip.

3. Overdue Fines & Lost Book Policy:
   • A nominal late fine of ₹2 per day per book is levied after the expiration of the due date.
   • If an issued book is lost or physically damaged:
     - The student is required to replace the book with a brand-new copy of the same or latest edition.
     - Alternatively, the student may pay the current publisher list price plus a 15% procurement and cataloging surcharge.
   • All library dues must be cleared prior to mid-semester and end-semester hall ticket generation.
   • Library Working Hours: Monday to Saturday: 8:00 AM – 8:00 PM | Reading Hall during exam weeks: Open until 11:00 PM."""
        },
        {
            "title": "How do I access IEEE Xplore, ScienceDirect, and digital e-resources off-campus?",
            "category_name": "Library & Study Material",
            "views": 47,
            "helpful_yes": 35,
            "helpful_no": 1,
            "deflections": 14,
            "days_ago": 15,
            "body": """Guide to accessing university-subscribed academic journals, e-books, and research databases remotely:

1. Available Subscriptions & Databases:
   • IEEE Xplore Digital Library (Engineering, Computer Science, Electronics)
   • ScienceDirect / Elsevier (Sciences, Medicine, Technology)
   • SpringerLink & ACM Digital Library
   • J-GATE, Scopus, and Web of Science indexing
   • National Digital Library of India (NDLI) portal integration

2. Method 1 — Institutional Email Single Sign-On (Shibboleth / OpenAthens):
   • Navigate to the publisher platform (e.g. https://ieeexplore.ieee.org or https://www.sciencedirect.com).
   • Click "Sign In" at the top right, then choose "Sign In via Your Institution".
   • Search for your university name and select it.
   • Enter your official @student.edu email and password. You will receive full PDF download access.

3. Method 2 — Campus VPN / EZProxy Remote Access:
   • Visit the Library Remote Portal at https://library.college.edu/remote.
   • Log in using your centralized student enrollment credentials.
   • All outbound search queries through this portal are automatically routed through the campus institutional IP range.

4. Past Examination Question Papers & Syllabus Repository:
   • The Central Library archives the last 5 years of university question papers sorted by branch and semester.
   • Access the repository on the campus intranet: http://172.16.1.10/question-bank or via the Student Portal under "Academic Resources".
   • For assistance, visit the Digital Library Section (1st Floor, Central Library) or contact library@college.edu."""
        },

        # --- General / Institutional Policies (All Categories) ---
        {
            "title": "How does the Grievance360 ticket resolution, SLA, and auto-escalation process work?",
            "category_name": None,
            "views": 94,
            "helpful_yes": 73,
            "helpful_no": 2,
            "deflections": 39,
            "days_ago": 30,
            "body": """A complete guide to understanding how your complaints are received, routed, resolved, and escalated:

1. Transparent Ticket Lifecycle:
   • Pending: Ticket logged. The system verifies category details and duplicate similarity against recent open complaints.
   • Assigned: Smart Dispatch routes the complaint to the designated department officer and staff technician with balanced workload distribution.
   • In Progress: The assigned staff member has reviewed the issue and work is actively underway.
   • Resolved: Staff has finished the necessary repairs or action and submitted closing remarks with before/after documentation.
   • Closed: The student accepts the resolution, or the system auto-closes the ticket after 5 days of inactivity.

2. Service Level Agreement (SLA) Deadlines by Category:
   • Internet & Computer Lab: 2 Calendar Days
   • Cleanliness & Hygiene: 3 Calendar Days
   • Hostel & Canteen: 4 Calendar Days
   • Infrastructure & Maintenance: 5 Calendar Days
   • Examination & Results: 7 Calendar Days
   • Library & Study Material: 10 Calendar Days
   • Emergency Triage (Anti-Ragging, Safety Hazards, Flood): Accelerated to 24-hour turnaround.

3. Multi-Tier Automated Escalation:
   • Pre-Breach Warning: When 75% of the SLA deadline has elapsed without resolution, an automated reminder is dispatched to the assigned staff.
   • Level 1 Escalation: If the deadline passes without resolution, the ticket is flagged as "BREACHED" and escalated to the Department Head / Chief Warden.
   • Level 2 Escalation: Continued stalling triggers automatic notification to the University Ombudsman / Institutional Grievance Redressal Committee.

4. Unsatisfied with the Resolution? Reopen within 5 Days:
   • If a technician marked your complaint "Resolved" but the issue persists, click "Reopen Complaint" within 5 days.
   • Reopened tickets receive an immediate priority score multiplier and supervisor audit."""
        },
        {
            "title": "What is the university's zero-tolerance policy on ragging and harassment?",
            "category_name": None,
            "views": 105,
            "helpful_yes": 88,
            "helpful_no": 0,
            "deflections": 45,
            "days_ago": 30,
            "body": """Our campus is dedicated to maintaining a safe, inclusive, and harassment-free academic environment:

1. Definition of Ragging (UGC Regulations & Statutory Law):
   • Any conduct by words spoken or written, or any act that teasing, treating, or handling any student with rudeness.
   • Forcing any student to perform an act that causes physical, emotional, or psychological discomfort, humiliation, or fear.
   • Indulging in rowdy or undisciplined activities causing hardship or psychological detriment to fresher or senior students.
   • Ragging is a cognizable criminal offense punishable under Indian Penal Code sections with immediate expulsion, degree cancellation, and police FIR.

2. Confidential & Emergency Reporting Channels:
   • Grievance360 Emergency Triage: Raise a complaint under any category with the word "Ragging" or "Emergency". The system automatically sets Emergency Priority, alerts the Anti-Ragging Squad, and initiates a 24-hour action window.
   • Anonymous Reporting: You can check "Submit Anonymously" on the raise complaint form — staff and committees will not see your identity, but your complaint will be investigated with maximum urgency.
   • 24/7 National Anti-Ragging Helpline: 1800-180-5522 (Toll-Free, 24 Hours) | helpline@antiragging.in
   • Campus Anti-Ragging Squad Helpline: Dial Ext. 1111 / Mobile: +91-2697-265111.
   • Internal Complaints Committee (ICC) for Women: Contact the Presiding Officer directly at icc@college.edu or Room 202, Admin Block.

3. Strict Protection for Whistleblowers:
   • The identity of students reporting ragging or harassment is protected under strict institutional non-retaliation policies.
   • Any intimidation, threat, or retaliation against a complainant results in immediate suspension and disciplinary action."""
        }
    ]

    inserted_count = 0
    updated_count = 0
    
    for item in ARTICLES_DATA:
        cat_id = cats.get(item["category_name"]) if item["category_name"] else None
        pub_dt = now - timedelta(days=item.get("days_ago", 10))
        pub_str = pub_dt.strftime(helpers.DT_FORMAT)
        
        doc = {
            "title": item["title"],
            "body": item["body"].strip(),
            "category_id": cat_id,
            "is_published": 1,
            "views": item.get("views", 15),
            "helpful_yes": item.get("helpful_yes", 10),
            "helpful_no": item.get("helpful_no", 0),
            "deflections": item.get("deflections", 5),
            "author_id": admin_id,
            "published_at": pub_str
        }
        
        existing = db_conn.kb_articles.find_one({"title": item["title"]})
        if existing:
            db_conn.kb_articles.update_one(
                {"_id": existing["_id"]},
                {"$set": doc}
            )
            updated_count += 1
            print(f"Updated: {item['title'][:50]}...")
        else:
            db_conn.kb_articles.insert_one(doc)
            inserted_count += 1
            print(f"Inserted: {item['title'][:50]}...")
            
    print(f"\nDone! Inserted: {inserted_count}, Updated: {updated_count}. Total articles in DB: {db_conn.kb_articles.count_documents({})}")

if __name__ == "__main__":
    seed_articles()
