"""Persistencia SQLite del prototipo, usando consultas parametrizadas."""
import os
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent

def database_path():
    return Path(os.environ.get('SGRT_DB', str(BASE / 'data' / 'sistema.db')))

def connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def initialize():
    with connect() as conn:
        conn.executescript((BASE / 'schema.sql').read_text(encoding='utf-8'))

def one(sql, params=()):
    with connect() as conn:
        return conn.execute(sql, params).fetchone()

def all_rows(sql, params=()):
    with connect() as conn:
        return conn.execute(sql, params).fetchall()
