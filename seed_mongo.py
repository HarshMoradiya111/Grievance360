import os
from datetime import datetime
from pymongo import MongoClient
from werkzeug.security import generate_password_hash

import config

client = MongoClient(config.MONGO_URI)
db = client[config.MONGO_DB]

# Clear existing
db.users.drop()
db.categories.drop()
db.departments.drop()
db.complaints.drop()

stamp = datetime.now()

# 1. Departments
depts = [
    {"name": "Maintenance", "email": "maintenance@college.edu", "created_at": stamp},
    {"name": "IT Support", "email": "itsupport@college.edu", "created_at": stamp},
    {"name": "Academics", "email": "academics@college.edu", "created_at": stamp},
    {"name": "Hostel", "email": "hostel@college.edu", "created_at": stamp},
]
res = db.departments.insert_many(depts)
dept_map = {d["name"]: d["_id"] for d in depts}

# 2. Categories
cats = [
    {"name": "Infrastructure & Maintenance", "department_id": dept_map["Maintenance"], "sla_days": 5, "priority_weight": 3, "created_at": stamp},
    {"name": "Cleanliness & Hygiene", "department_id": dept_map["Maintenance"], "sla_days": 3, "priority_weight": 2, "created_at": stamp},
    {"name": "Internet & Computer Lab", "department_id": dept_map["IT Support"], "sla_days": 2, "priority_weight": 4, "created_at": stamp},
    {"name": "Examination & Results", "department_id": dept_map["Academics"], "sla_days": 7, "priority_weight": 5, "created_at": stamp},
    {"name": "Library & Study Material", "department_id": dept_map["Academics"], "sla_days": 10, "priority_weight": 1, "created_at": stamp},
    {"name": "Hostel & Canteen", "department_id": dept_map["Hostel"], "sla_days": 4, "priority_weight": 3, "created_at": stamp},
]
db.categories.insert_many(cats)

# 3. Users
users = [
    {"name": "System Admin", "email": "admin@grievance360.edu", "password_hash": generate_password_hash("admin123"), "role": "admin", "department_id": None, "enrollment_no": None, "is_active": True, "created_at": stamp},
    {"name": "Ramesh Patil", "email": "maintenance.staff@grievance360.edu", "password_hash": generate_password_hash("staff123"), "role": "staff", "department_id": dept_map["Maintenance"], "enrollment_no": None, "is_active": True, "created_at": stamp},
    {"name": "Neha Shah", "email": "it.staff@grievance360.edu", "password_hash": generate_password_hash("staff123"), "role": "staff", "department_id": dept_map["IT Support"], "enrollment_no": None, "is_active": True, "created_at": stamp},
    {"name": "Harsh Moradiya", "email": "harsh@student.edu", "password_hash": generate_password_hash("student123"), "role": "student", "department_id": None, "enrollment_no": "MSCIT2026001", "is_active": True, "created_at": stamp},
]
db.users.insert_many(users)

# 4. Knowledge Base Articles
from seed_kb_articles import seed_articles
seed_articles()

print("MongoDB Seeded successfully!")
