-- ===========================================================================
-- Grievance360 - MySQL schema
-- ---------------------------------------------------------------------------
-- This is the canonical schema for the project report / data dictionary.
-- To use it:   mysql -u root -p < database/schema.sql
-- Then set DB_ENGINE = "mysql" in config.py and run:  python init_db.py
-- ===========================================================================

DROP DATABASE IF EXISTS grievance360;
CREATE DATABASE grievance360 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE grievance360;

-- ---------------------------------------------------------------------------
-- 1. departments -- the offices that resolve complaints
-- ---------------------------------------------------------------------------
CREATE TABLE departments (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    email       VARCHAR(120),
    created_at  DATETIME NOT NULL
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 2. categories -- complaint types; each carries its own SLA and urgency
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    department_id   INT,
    sla_days        INT NOT NULL DEFAULT 7,   -- days allowed before breach
    priority_weight INT NOT NULL DEFAULT 1,   -- 1 = low .. 5 = critical
    created_at      DATETIME NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 3. users -- students, staff and admins all live in one table
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           ENUM('student','staff','admin') NOT NULL DEFAULT 'student',
    department_id  INT,                       -- only meaningful for staff
    enrollment_no  VARCHAR(50),               -- only meaningful for students
    phone          VARCHAR(20),
    is_active      TINYINT(1) NOT NULL DEFAULT 1,
    reset_token    VARCHAR(100),              -- password reset support
    reset_expires  DATETIME,
    created_at     DATETIME NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 4. complaints -- the heart of the system
-- ---------------------------------------------------------------------------
CREATE TABLE complaints (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    ticket_code    VARCHAR(20) NOT NULL UNIQUE,   -- GRV-2026-0001
    user_id        INT NOT NULL,                  -- who raised it
    category_id    INT NOT NULL,
    department_id  INT,                           -- filled on assignment
    assigned_to    INT,                           -- staff user id
    subject        VARCHAR(200) NOT NULL,
    description    TEXT NOT NULL,
    attachment     VARCHAR(255),                  -- filename in static/uploads
    is_anonymous   TINYINT(1) NOT NULL DEFAULT 0,
    status         VARCHAR(20) NOT NULL DEFAULT 'Pending',
    priority_score INT NOT NULL DEFAULT 0,
    reopen_count   INT NOT NULL DEFAULT 0,
    created_at     DATETIME NOT NULL,
    updated_at     DATETIME NOT NULL,
    deadline       DATETIME NOT NULL,             -- created_at + sla_days
    resolved_at    DATETIME,
    FOREIGN KEY (user_id)       REFERENCES users(id),
    FOREIGN KEY (category_id)   REFERENCES categories(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (assigned_to)   REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 5. complaint_status_history -- an audit trail of every status change
-- ---------------------------------------------------------------------------
CREATE TABLE complaint_status_history (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    old_status   VARCHAR(20),
    new_status   VARCHAR(20) NOT NULL,
    remark       TEXT,
    changed_by   INT,
    created_at   DATETIME NOT NULL,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (changed_by)   REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 6. comments -- conversation between student and staff on a ticket
-- ---------------------------------------------------------------------------
CREATE TABLE comments (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    user_id      INT NOT NULL,
    message      TEXT NOT NULL,
    created_at   DATETIME NOT NULL,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id)      REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 7. feedback -- star rating, only after a complaint is Resolved
-- ---------------------------------------------------------------------------
CREATE TABLE feedback (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL UNIQUE,   -- one rating per complaint
    user_id      INT NOT NULL,
    rating       INT NOT NULL,          -- 1..5
    remark       TEXT,
    created_at   DATETIME NOT NULL,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id)      REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 8. notifications -- feeds the live bell in the navbar
-- ---------------------------------------------------------------------------
CREATE TABLE notifications (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    complaint_id INT,
    message      VARCHAR(255) NOT NULL,
    link         VARCHAR(255),
    is_read      TINYINT(1) NOT NULL DEFAULT 0,
    created_at   DATETIME NOT NULL,
    FOREIGN KEY (user_id)      REFERENCES users(id),
    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
) ENGINE=InnoDB;


-- ---------------------------------------------------------------------------
-- 9. escalations -- one row per level change (module M9)
-- ---------------------------------------------------------------------------
CREATE TABLE escalations (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id     INT NOT NULL,
    from_level       INT NOT NULL,
    to_level         INT NOT NULL,
    reason           TEXT,
    notified_user_id INT,
    escalated_at     DATETIME NOT NULL,
    FOREIGN KEY (complaint_id)     REFERENCES complaints(id),
    FOREIGN KEY (notified_user_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 10. complaint_links -- a duplicate merged into a parent (module M10)
-- ---------------------------------------------------------------------------
CREATE TABLE complaint_links (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    parent_id  INT NOT NULL,
    child_id   INT NOT NULL UNIQUE,
    linked_by  INT,
    linked_at  DATETIME NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES complaints(id),
    FOREIGN KEY (child_id)  REFERENCES complaints(id),
    FOREIGN KEY (linked_by) REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 11. complaint_supporters -- endorsements of an existing complaint (M10)
-- ---------------------------------------------------------------------------
CREATE TABLE complaint_supporters (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    complaint_id INT NOT NULL,
    user_id      INT NOT NULL,
    supported_at DATETIME NOT NULL,
    UNIQUE KEY uq_supporter (complaint_id, user_id),
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id)      REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 12. kb_articles -- knowledge base (module M11)
-- ---------------------------------------------------------------------------
CREATE TABLE kb_articles (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    title        VARCHAR(200) NOT NULL,
    body         TEXT NOT NULL,
    category_id  INT,
    is_published TINYINT(1) NOT NULL DEFAULT 1,
    views        INT NOT NULL DEFAULT 0,
    helpful_yes  INT NOT NULL DEFAULT 0,
    helpful_no   INT NOT NULL DEFAULT 0,
    deflections  INT NOT NULL DEFAULT 0,
    author_id    INT,
    published_at DATETIME NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (author_id)   REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- 13. announcements -- notice board (module M12)
-- ---------------------------------------------------------------------------
CREATE TABLE announcements (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    title         VARCHAR(200) NOT NULL,
    body          TEXT NOT NULL,
    audience_role VARCHAR(20) NOT NULL DEFAULT 'all',
    department_id INT,
    category_id   INT,
    starts_at     DATETIME NOT NULL,
    ends_at       DATETIME NOT NULL,
    is_active     TINYINT(1) NOT NULL DEFAULT 1,
    author_id     INT,
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (category_id)   REFERENCES categories(id),
    FOREIGN KEY (author_id)     REFERENCES users(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- Indexes -- these columns are filtered/searched constantly
-- ---------------------------------------------------------------------------
CREATE INDEX idx_complaints_ticket    ON complaints(ticket_code);
CREATE INDEX idx_complaints_status    ON complaints(status);
CREATE INDEX idx_complaints_category  ON complaints(category_id);
CREATE INDEX idx_complaints_user      ON complaints(user_id);
CREATE INDEX idx_complaints_assigned  ON complaints(assigned_to);
CREATE INDEX idx_complaints_dept      ON complaints(department_id);
CREATE INDEX idx_complaints_deadline  ON complaints(deadline);
CREATE INDEX idx_users_email          ON users(email);
CREATE INDEX idx_history_complaint    ON complaint_status_history(complaint_id);
CREATE INDEX idx_comments_complaint   ON comments(complaint_id);
CREATE INDEX idx_notif_user_unread    ON notifications(user_id, is_read);
CREATE INDEX idx_escalations_complaint ON escalations(complaint_id);
CREATE INDEX idx_links_parent          ON complaint_links(parent_id);
CREATE INDEX idx_supporters_complaint  ON complaint_supporters(complaint_id);
CREATE INDEX idx_kb_published          ON kb_articles(is_published);
CREATE INDEX idx_ann_window            ON announcements(is_active, starts_at, ends_at);


-- ===========================================================================
-- Seed data is inserted by init_db.py so that passwords are properly hashed
-- by Werkzeug rather than pasted in as plain text.
-- ===========================================================================
