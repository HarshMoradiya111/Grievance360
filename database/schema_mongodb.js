// MongoDB Schema equivalents for Grievance360
// Run this script in the mongosh shell to set up collections with validation

const dbName = 'grievance360';
use(dbName);

// 1. Departments Collection
db.createCollection("departments", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "created_at"],
      properties: {
        name: { bsonType: "string", description: "Must be a string and is required" },
        created_at: { bsonType: "date" }
      }
    }
  }
});
db.departments.createIndex({ name: 1 }, { unique: true });

// 2. Categories Collection
db.createCollection("categories", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "sla_days", "priority_weight", "created_at"],
      properties: {
        name: { bsonType: "string" },
        department_id: { bsonType: "objectId" }, // References departments
        sla_days: { bsonType: "int" },
        priority_weight: { bsonType: "int" },
        created_at: { bsonType: "date" }
      }
    }
  }
});
db.categories.createIndex({ name: 1 }, { unique: true });

// 3. Users Collection
db.createCollection("users", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["name", "email", "password_hash", "role", "is_active", "created_at"],
      properties: {
        name: { bsonType: "string" },
        email: { bsonType: "string" },
        password_hash: { bsonType: "string" },
        role: { enum: ["student", "staff", "admin"] },
        department_id: { bsonType: "objectId" }, // For staff
        enrollment_no: { bsonType: "string" }, // For students
        phone: { bsonType: "string" },
        is_active: { bsonType: "bool" },
        reset_token: { bsonType: "string" },
        reset_expires: { bsonType: "date" },
        created_at: { bsonType: "date" }
      }
    }
  }
});
db.users.createIndex({ email: 1 }, { unique: true });

// 4. Complaints Collection
db.createCollection("complaints", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["ticket_code", "user_id", "category_id", "status", "title", "description", "priority_score", "created_at"],
      properties: {
        ticket_code: { bsonType: "string" },
        user_id: { bsonType: "objectId" }, // References users
        category_id: { bsonType: "objectId" }, // References categories
        department_id: { bsonType: "objectId" }, // References departments
        assigned_to: { bsonType: "objectId" }, // References users (staff)
        status: { enum: ["Pending", "Assigned", "In Progress", "Resolved", "Closed", "Reopened", "Rejected"] },
        title: { bsonType: "string" },
        description: { bsonType: "string" },
        attachment_path: { bsonType: "string" },
        priority_score: { bsonType: "int" },
        reopen_count: { bsonType: "int" },
        deadline: { bsonType: "date" },
        created_at: { bsonType: "date" },
        updated_at: { bsonType: "date" },
        
        // Embedded arrays for related data (instead of separate tables)
        status_history: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["status", "changed_at"],
            properties: {
              status: { bsonType: "string" },
              changed_by: { bsonType: "objectId" },
              notes: { bsonType: "string" },
              changed_at: { bsonType: "date" }
            }
          }
        },
        comments: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["user_id", "message", "created_at"],
            properties: {
              user_id: { bsonType: "objectId" },
              message: { bsonType: "string" },
              created_at: { bsonType: "date" }
            }
          }
        },
        feedback: {
          bsonType: "object",
          properties: {
            rating: { bsonType: "int" },
            comments: { bsonType: "string" },
            created_at: { bsonType: "date" }
          }
        }
      }
    }
  }
});
db.complaints.createIndex({ ticket_code: 1 }, { unique: true });
db.complaints.createIndex({ user_id: 1 });
db.complaints.createIndex({ department_id: 1 });
db.complaints.createIndex({ assigned_to: 1 });
db.complaints.createIndex({ status: 1 });

// 5. Notifications Collection
db.createCollection("notifications", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id", "message", "is_read", "created_at"],
      properties: {
        user_id: { bsonType: "objectId" },
        complaint_id: { bsonType: "objectId" },
        message: { bsonType: "string" },
        is_read: { bsonType: "bool" },
        created_at: { bsonType: "date" }
      }
    }
  }
});
db.notifications.createIndex({ user_id: 1, is_read: 1 });
