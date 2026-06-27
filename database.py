import sqlite3, os
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "bot.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        allowed INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS allowed_usernames (username TEXT PRIMARY KEY)""")
    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, author_username TEXT,
        platform TEXT, price TEXT, description TEXT, channel_id TEXT, message_id INTEGER,
        status TEXT DEFAULT 'active', auto_delete_at TEXT, created_at TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT UNIQUE,
        channel_name TEXT, added_at TEXT DEFAULT (datetime('now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    defaults = {
        "btn_post":"📝 Выложить задание","btn_stats":"📊 Статистика","btn_delete":"🗑 Удалить задание",
        "btn_yandex":"🗺 Яндекс Карты","btn_2gis":"🗺 2ГИС","btn_google":"🗺 Гугл Карты",
        "btn_avito":"🛍 Авито","btn_other":"✏️ Другое",
        "ch_btn_contact":"Написать","ch_btn_payment":"Выплаты","ch_btn_learn":"Обучение",
        "link_payment":"","link_learn":"",
        "prices_yandex":"120₽,150₽,200₽","prices_2gis":"10₽,20₽",
        "prices_avito":"200₽,300₽,400₽,500₽","prices_google":"40₽,60₽,100₽",
        "task_template":"НОВОЕ ЗАДАНИЕ!\n\n• Платформа: {platform}\n• Оплата: {price}\n• Описание: {description}\n\n𖥔 — · ──  ·  easy money  ·  ── · — 𖥔",
        "closed_template":"🔓Данное задание закончилось, дождитесь следующего, чтобы приступить к работе!\n\n𖥔 — · ──  ·  easy money  ·  ── · — 𖥔",
    }
    for k,v in defaults.items():
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)",(k,v))
    conn.commit(); conn.close()

def upsert_user(user_id, username, first_name):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users (user_id,username,first_name) VALUES (?,?,?)",(user_id,username or "",first_name or ""))
    conn.execute("UPDATE users SET username=?,first_name=? WHERE user_id=?",(username or "",first_name or "",user_id))
    if username:
        pre = conn.execute("SELECT username FROM allowed_usernames WHERE username=?",(username.lower(),)).fetchone()
        if pre: conn.execute("UPDATE users SET allowed=1 WHERE user_id=?",(user_id,))
    conn.commit(); conn.close()

def is_allowed(user_id):
    conn = get_conn()
    row = conn.execute("SELECT allowed FROM users WHERE user_id=?",(user_id,)).fetchone()
    conn.close(); return bool(row and row["allowed"]==1)

def set_allowed(user_id, allowed):
    conn = get_conn()
    conn.execute("UPDATE users SET allowed=? WHERE user_id=?",(1 if allowed else 0,user_id))
    conn.commit(); conn.close()

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_allowed_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users WHERE allowed=1 AND user_id>0").fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_user_by_username(username):
    username = username.lstrip("@").lower()
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE LOWER(username)=?",(username,)).fetchone()
    conn.close(); return dict(row) if row else None

def add_user_by_username(username):
    username = username.lstrip("@").lower()
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO allowed_usernames (username) VALUES (?)",(username,))
    conn.execute("UPDATE users SET allowed=1 WHERE LOWER(username)=?",(username,))
    conn.commit(); conn.close()

def create_task(user_id, author_username, platform, price, description, channel_id, message_id, auto_delete_at=None):
    conn = get_conn()
    c = conn.execute("INSERT INTO tasks (user_id,author_username,platform,price,description,channel_id,message_id,auto_delete_at) VALUES (?,?,?,?,?,?,?,?)",
        (user_id,author_username,platform,price,description,channel_id,message_id,auto_delete_at))
    tid = c.lastrowid; conn.commit(); conn.close(); return tid

def get_active_tasks(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tasks WHERE user_id=? AND status='active' ORDER BY created_at DESC",(user_id,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_task(task_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
    conn.close(); return dict(row) if row else None

def close_task(task_id):
    conn = get_conn()
    conn.execute("UPDATE tasks SET status='closed' WHERE id=?",(task_id,))
    conn.commit(); conn.close()

def get_tasks_to_auto_delete():
    conn = get_conn()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("SELECT * FROM tasks WHERE status='active' AND auto_delete_at IS NOT NULL AND auto_delete_at<=?",(now,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_all_active_tasks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tasks WHERE status='active' ORDER BY created_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def add_channel(channel_id, channel_name):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO channels (channel_id,channel_name) VALUES (?,?)",(channel_id,channel_name))
    conn.commit(); conn.close()

def get_channels():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM channels ORDER BY added_at DESC").fetchall()
    conn.close(); return [dict(r) for r in rows]

def delete_channel(channel_id):
    conn = get_conn()
    conn.execute("DELETE FROM channels WHERE channel_id=?",(channel_id,))
    conn.commit(); conn.close()

def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
    conn.close(); return row["value"] if row else default

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",(key,value))
    conn.commit(); conn.close()

def get_prices(platform_key):
    val = get_setting(f"prices_{platform_key}","")
    return [p.strip() for p in val.split(",") if p.strip()]

def get_stats():
    conn = get_conn()
    s = {"total_users":conn.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"],
         "allowed_users":conn.execute("SELECT COUNT(*) as n FROM users WHERE allowed=1").fetchone()["n"],
         "total_tasks":conn.execute("SELECT COUNT(*) as n FROM tasks").fetchone()["n"],
         "active_tasks":conn.execute("SELECT COUNT(*) as n FROM tasks WHERE status='active'").fetchone()["n"]}
    conn.close(); return s
