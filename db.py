"""Database layer for MongoDB."""

from flask import g
import config
from pymongo import MongoClient

_mongo_client = None

def get_mongo_client():
    """Return a cached MongoClient instance for efficient serverless connection reuse."""
    global _mongo_client
    if _mongo_client is None:
        if config.DB_ENGINE == "mongodb":
            _mongo_client = MongoClient(
                config.MONGO_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000
            )
        else:
            raise ValueError("Only 'mongodb' is supported as DB_ENGINE")
    return _mongo_client

def _connect():
    """Return the MongoDB database handle."""
    client = get_mongo_client()
    return client[config.MONGO_DB]

def get_db():
    """Return the connection for this web request, opening it if needed."""
    if "db" not in g:
        g.db = _connect()
    return g.db

def close_db(error=None):
    """Called automatically by Flask when a request finishes.
    In PyMongo, the MongoClient connection pool is shared across requests."""
    g.pop("db", None)

def init_app(app):
    """Register close_db so request context is cleanly released."""
    app.teardown_appcontext(close_db)
