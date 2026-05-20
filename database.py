import csv
import io
import os
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL")


def _get_conn():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("registrations.db")


def _ph():
    return "%s" if DATABASE_URL else "?"


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    if DATABASE_URL:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id SERIAL PRIMARY KEY, telegram_id BIGINT UNIQUE,
                username TEXT, full_name TEXT, interests TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                key TEXT PRIMARY KEY, topic TEXT, date TEXT,
                location TEXT, map TEXT, is_active BOOLEAN DEFAULT TRUE)""")
        cur.execute("""
            INSERT INTO events (key,topic,date,location,map,is_active)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (key) DO NOTHING""",
            ("current","Claude Code — как создавать приложения и сайты без навыков программирования",
             "Скоро — следи за анонсами","—","",True))
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE,
                username TEXT, full_name TEXT, interests TEXT,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                key TEXT PRIMARY KEY, topic TEXT, date TEXT,
                location TEXT, map TEXT, is_active INTEGER DEFAULT 1)""")
        cur.execute("""
            INSERT OR IGNORE INTO events (key,topic,date,location,map,is_active)
            VALUES (?,?,?,?,?,?)""",
            ("current","Claude Code — как создавать приложения и сайты без навыков программирования",
             "Скоро — следи за анонсами","—","",1))
    conn.commit()
    conn.close()


def save_registration(telegram_id, username, full_name, interests):
    ph = _ph()
    conn = _get_conn()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute(f"""INSERT INTO registrations (telegram_id,username,full_name,interests)
            VALUES ({ph},{ph},{ph},{ph})
            ON CONFLICT (telegram_id) DO UPDATE SET
            username=EXCLUDED.username, full_name=EXCLUDED.full_name,
            interests=EXCLUDED.interests, registered_at=CURRENT_TIMESTAMP""",
            (telegram_id, username, full_name, interests))
    else:
        cur.execute(f"""INSERT INTO registrations (telegram_id,username,full_name,interests)
            VALUES ({ph},{ph},{ph},{ph})
            ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username, full_name=excluded.full_name,
            interests=excluded.interests, registered_at=CURRENT_TIMESTAMP""",
            (telegram_id, username, full_name, interests))
    conn.commit()
    conn.close()


def get_all_registrations():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id,full_name,username,interests,registered_at FROM registrations ORDER BY registered_at")
    rows = [(r[0], r[1], r[2], r[3], str(r[4])[:16]) for r in cur.fetchall()]
    conn.close()
    return rows


def get_all_telegram_ids():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM registrations")
    ids = [r[0] for r in cur.fetchall()]
    conn.close()
    return ids


def get_count():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM registrations")
    count = cur.fetchone()[0]
    conn.close()
    return count


def export_csv():
    rows = get_all_registrations()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["#","Имя","Username","Интересы","Дата"])
    for r in rows:
        w.writerow(r)
    return out.getvalue().encode("utf-8-sig")


def get_event():
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT topic,date,location,map,is_active FROM events WHERE key={ph}", ("current",))
    row = cur.fetchone()
    conn.close()
    if not row:
        return {"topic":"Скоро","date":"—","location":"—","map":"","is_active":False}
    return {"topic":row[0],"date":row[1],"location":row[2],"map":row[3] or "","is_active":bool(row[4])}


def save_event(topic, date, location, map_url):
    ph = _ph()
    conn = _get_conn()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("""INSERT INTO events (key,topic,date,location,map,is_active)
            VALUES (%s,%s,%s,%s,%s,TRUE) ON CONFLICT (key) DO UPDATE SET
            topic=EXCLUDED.topic,date=EXCLUDED.date,
            location=EXCLUDED.location,map=EXCLUDED.map,is_active=TRUE""",
            ("current",topic,date,location,map_url))
    else:
        cur.execute("""INSERT INTO events (key,topic,date,location,map,is_active)
            VALUES (?,?,?,?,?,1) ON CONFLICT(key) DO UPDATE SET
            topic=excluded.topic,date=excluded.date,
            location=excluded.location,map=excluded.map,is_active=1""",
            ("current",topic,date,location,map_url))
    conn.commit()
    conn.close()


def set_event_active(is_active):
    ph = _ph()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE events SET is_active={ph} WHERE key={ph}", (is_active,"current"))
    conn.commit()
    conn.close()
