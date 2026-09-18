-- ===========================================================================
-- Grievance360 - SQLite schema
-- ---------------------------------------------------------------------------
-- Same 8 tables as database/schema.sql, translated for SQLite so the project
-- runs with no database server installed. Differences are only in TYPE names:
--     INT AUTO_INCREMENT PRIMARY KEY  ->  INTEGER PRIMARY KEY AUTOINCREMENT
--     ENUM(...)                       ->  TEXT + CHECK constraint
--     DATETIME                        ->  TEXT (ISO 'YYYY-MM-DD HH:MM:SS')
--     TINYINT(1)                      ->  INTEGER (0/1)
-- The column names, keys and indexes are identical, so every query in the
-- app works unchanged against either engine.
--
-- Applied automatically by:  python init_db.py
-- ===========================================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS announcements;
DROP TABLE IF EXISTS kb_articles;
DROP TABLE IF EXISTS complaint_supporters;
DROP TABLE IF EXISTS complaint_links;
DROP TABLE IF EXISTS escalations;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS complaint_status_history;
DROP TABLE IF EXISTS complaints;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS departments;

-- 1. departments -------------------------------------------------------------
CREATE TABLE departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    email       TEXT,
    created_at  TEXT NOT NULL
);

-- 2. categories --------------------------------------------------------------
CREATE TABLE categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    department_id   INTEGER,
    sla_days        INTEGER NOT NULL DEFAULT 7,
    priority_weight INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- 3. users -------------------------------------------------------------------
CREATE TABLE users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    role           TEXT NOT NULL DEFAULT 'student'
                   CHECK (role IN ('student','staff','admin')),
    department_id  INTEGER,
    enrollment_no  TEXT,
    phone          TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1,
    reset_token    TEXT,
    reset_expires  TEXT,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

-- 4. complaints --------------------------------------------------------------
CREATE TABLE complaints (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_code    TEXT NOT NULL UNIQUE,
    user_id        INTEGER NOT NULL,
    category_id    INTEGER NOT NULL,
    department_id  INTEGER,
    assigned_to    INTEGER,
    subject        TEXT NOT NULL,
    description    TEXT NOT NULL,
    attachment     TEXT,
    is_anonymous   INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'Pending',
    priority_score INTEGER NOT NULL DEFAULT 0,
    reopen_count   INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    deadline       TEXT NOT NULL,
    resolved_at    TEXT,
    FOREIGN KEY (user_id)       REFERENCES users(id),
    FOREIGN KEY (category_id)   REFERENCES categories(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (assigned_to)   REFERENCES users(id)
);

-- 5. complaint_status_history ------------------------------------------------
CREATE TABLE complaint_status_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL,
    old_status   TEXT,
    new_status   TEXT NOT NULL,
    remark       TEXT,
    changed_by   INTEGER,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (changed_by)   REFERENCES users(id)
);

-- 6. comments ----------------------------------------------------------------
CREATE TABLE comments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    message      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id)      REFERENCES users(id)
);

-- 7. feedback ----------------------------------------------------------------
CREATE TABLE feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL UNIQUE,
    user_id      INTEGER NOT NULL,
    rating       INTEGER NOT NULL,
    remark       TEXT,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id)      REFERENCES users(id)
);

-- 8. notifications -----------------------------------------------------------
CREATE TABLE notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    complaint_id INTEGER,
    message      TEXT NOT NULL,
    link         TEXT,
    is_read      INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    FOREIGN KEY (user_id)      REFERENCES users(id),
    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
);


-- 9. escalations (module M9) -------------------------------------------------
CREATE TABLE escalations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id     INTEGER NOT NULL,
    from_level       INTEGER NOT NULL,
    to_level         INTEGER NOT NULL,
    reason           TEXT,
    notified_user_id INTEGER,
    escalated_at     TEXT NOT NULL,
    FOREIGN KEY (complaint_id)     REFERENCES complaints(id),
    FOREIGN KEY (notified_user_id) REFERENCES users(id)
);

-- 10. complaint_links (module M10) -------------------------------------------
CREATE TABLE complaint_links (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER NOT NULL,
    child_id   INTEGER NOT NULL UNIQUE,
    linked_by  INTEGER,
    linked_at  TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES complaints(id),
    FOREIGN KEY (child_id)  REFERENCES complaints(id),
    FOREIGN KEY (linked_by) REFERENCES users(id)
);

-- 11. complaint_supporters (module M10) --------------------------------------
CREATE TABLE complaint_supporters (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    supported_at TEXT NOT NULL,
    UNIQUE (complaint_id, user_id),
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id)      REFERENCES users(id)
);

-- 12. kb_articles (module M11) -----------------------------------------------
CREATE TABLE kb_articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    body         TEXT NOT NULL,
    category_id  INTEGER,
    is_published INTEGER NOT NULL DEFAULT 1,
    views        INTEGER NOT NULL DEFAULT 0,
    helpful_yes  INTEGER NOT NULL DEFAULT 0,
    helpful_no   INTEGER NOT NULL DEFAULT 0,
    deflections  INTEGER NOT NULL DEFAULT 0,
    author_id    INTEGER,
    published_at TEXT NOT NULL,
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (author_id)   REFERENCES users(id)
);

-- 13. announcements (module M12) ---------------------------------------------
CREATE TABLE announcements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    audience_role TEXT NOT NULL DEFAULT 'all',
    department_id INTEGER,
    category_id   INTEGER,
    starts_at     TEXT NOT NULL,
    ends_at       TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    author_id     INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (category_id)   REFERENCES categories(id),
    FOREIGN KEY (author_id)     REFERENCES users(id)
);

-- Indexes --------------------------------------------------------------------
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

