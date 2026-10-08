"""Database layer for MongoDB."""

from flask import g
import config
from pymongo import MongoClient

def _connect():
    """Open a brand new connection to MongoDB."""
    if config.DB_ENGINE == "mongodb":
        client = MongoClient(config.MONGO_URI)
        return client[config.MONGO_DB]
    raise ValueError("Only 'mongodb' is supported as DB_ENGINE")

def get_db():
    """Return the connection for this web request, opening it if needed."""
    if "db" not in g:
        g.db = _connect()
    return g.db

def close_db(error=None):
    """Called automatically by Flask when a request finishes.
    In PyMongo, you generally don't need to close connections per request
    due to connection pooling, but we can clean up the flask g object."""
    g.pop("db", None)

def init_app(app):
    """Register close_db so connections never leak between requests."""
    app.teardown_appcontext(close_db)
