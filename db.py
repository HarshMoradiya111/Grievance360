"""Database layer. All queries go through here.
%s placeholders rewritten to ? for SQLite; every row returned as a dict."""

import sqlite3

from flask import g

import config


# ---------------------------------------------------------------------------
# SQLite compatibility wrapper
# ---------------------------------------------------------------------------
class _SQLiteCursor:
    """Makes a sqlite3 cursor behave like a PyMySQL DictCursor."""

    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=()):
        # MySQL uses %s for placeholders, SQLite uses ?. Rewrite them.
        # Note: we never put a literal % inside SQL text -- LIKE patterns are
        # always passed in as parameters -- so this swap is always safe.
        return self._cursor.execute(sql.replace("%s", "?"), params)

    def fetchone(self):
        row = self._cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(row) for row in self._cursor.fetchall()]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class _SQLiteConnection:
    """Wraps a sqlite3 connection so .cursor() returns our dict-style cursor."""

    def __init__(self, connection):
        self._connection = connection

    def cursor(self):
        return _SQLiteCursor(self._connection.cursor())

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------
def _connect():
    """Open a brand new connection using whichever engine config.py names."""
    if config.DB_ENGINE == "sqlite":
        raw = sqlite3.connect(config.SQLITE_PATH)
        raw.row_factory = sqlite3.Row          # lets us build dicts from rows
        raw.execute("PRAGMA foreign_keys = ON")  # SQLite needs this switched on
        return _SQLiteConnection(raw)

    if config.DB_ENGINE == "mysql":
        import pymysql
        import pymysql.cursors

        return pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            charset="utf8mb4",
        )

    raise ValueError(
        "config.DB_ENGINE must be 'sqlite' or 'mysql', got %r" % config.DB_ENGINE
    )


def get_db():
    """Return the connection for this web request, opening it if needed."""
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(error=None):
    """Called automatically by Flask when a request finishes."""
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


# ---------------------------------------------------------------------------
# Small query helpers -- these keep the routes short and readable
# ---------------------------------------------------------------------------
def query_all(sql, params=()):
    """Run a SELECT and return a list of dicts (empty list if nothing found)."""
    cursor = get_db().cursor()
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return rows


def query_one(sql, params=()):
    """Run a SELECT and return the first row as a dict, or None."""
    cursor = get_db().cursor()
    cursor.execute(sql, params)
    row = cursor.fetchone()
    cursor.close()
    return row


def execute(sql, params=()):
    """Run an INSERT/UPDATE/DELETE, commit it, and return the new row id."""
    connection = get_db()
    cursor = connection.cursor()
    cursor.execute(sql, params)
    new_id = cursor.lastrowid
    connection.commit()
    cursor.close()
    return new_id


def init_app(app):
    """Register close_db so connections never leak between requests."""
    app.teardown_appcontext(close_db)
