import sqlite3, os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "sialens.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        subscription TEXT DEFAULT 'none', trial_start TEXT, had_trial INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS mutes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER, muted_user_id INTEGER, muted_username TEXT,
        conn_id TEXT, muted_at TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER, warned_user_id INTEGER, warned_username TEXT,
        count INTEGER DEFAULT 1)""")
    conn.commit(); conn.close()

def upsert_user(user_id, username, first_name):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users (user_id,username,first_name) VALUES (?,?,?)",
                 (user_id, username or "", first_name or ""))
    conn.execute("UPDATE users SET username=?,first_name=? WHERE user_id=?",
                 (username or "", first_name or "", user_id))
    conn.commit(); conn.close()

def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close(); return dict(row) if row else None

def get_user_by_username(username):
    username = username.lstrip("@").lower()
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE LOWER(username)=?", (username,)).fetchone()
    conn.close(); return dict(row) if row else None

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def set_subscription(user_id, sub_type):
    conn = get_conn()
    conn.execute("UPDATE users SET subscription=? WHERE user_id=?", (sub_type, user_id))
    conn.commit(); conn.close()

def set_trial(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET subscription='trial', trial_start=?, had_trial=1 WHERE user_id=?",
                 (datetime.now().isoformat(), user_id))
    conn.commit(); conn.close()

def add_mute(owner_id, muted_user_id, muted_username, conn_id):
    conn = get_conn()
    conn.execute("DELETE FROM mutes WHERE owner_id=? AND muted_user_id=?", (owner_id, muted_user_id))
    conn.execute("INSERT INTO mutes (owner_id,muted_user_id,muted_username,conn_id) VALUES (?,?,?,?)",
                 (owner_id, muted_user_id, muted_username, conn_id))
    conn.commit(); conn.close()

def remove_mute(owner_id, muted_user_id):
    conn = get_conn()
    conn.execute("DELETE FROM mutes WHERE owner_id=? AND muted_user_id=?", (owner_id, muted_user_id))
    conn.commit(); conn.close()

def is_muted(owner_id, user_id):
    conn = get_conn()
    row = conn.execute("SELECT id FROM mutes WHERE owner_id=? AND muted_user_id=?", (owner_id, user_id)).fetchone()
    conn.close(); return row is not None

def get_mutes(owner_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM mutes WHERE owner_id=?", (owner_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_user_mutes_count(owner_id):
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) as n FROM mutes WHERE owner_id=?", (owner_id,)).fetchone()["n"]
    conn.close(); return n

def add_warn(owner_id, warned_user_id, warned_username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM warnings WHERE owner_id=? AND warned_user_id=?",
                       (owner_id, warned_user_id)).fetchone()
    if row:
        new_count = min(row["count"] + 1, 3)
        conn.execute("UPDATE warnings SET count=? WHERE owner_id=? AND warned_user_id=?",
                     (new_count, owner_id, warned_user_id))
    else:
        new_count = 1
        conn.execute("INSERT INTO warnings (owner_id,warned_user_id,warned_username,count) VALUES (?,?,?,1)",
                     (owner_id, warned_user_id, warned_username))
    conn.commit(); conn.close()
    return new_count

def get_warns(owner_id, warned_user_id):
    conn = get_conn()
    row = conn.execute("SELECT count FROM warnings WHERE owner_id=? AND warned_user_id=?",
                       (owner_id, warned_user_id)).fetchone()
    conn.close(); return row["count"] if row else 0

def get_all_warns(owner_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM warnings WHERE owner_id=?", (owner_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_user_warns_count(owner_id):
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) as n FROM warnings WHERE owner_id=?", (owner_id,)).fetchone()["n"]
    conn.close(); return n

def get_stats():
    conn = get_conn()
    total      = conn.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    subscribed = conn.execute("SELECT COUNT(*) as n FROM users WHERE subscription='forever'").fetchone()["n"]
    trial      = conn.execute("SELECT COUNT(*) as n FROM users WHERE subscription='trial'").fetchone()["n"]
    free       = conn.execute("SELECT COUNT(*) as n FROM users WHERE subscription='free'").fetchone()["n"]
    conn.close()
    return {"total": total, "subscribed": subscribed, "trial": trial, "free": free}
