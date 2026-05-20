"""
База данных: PostgreSQL (Railway) или SQLite (локально).
Railway автоматически даёт DATABASE_URL при подключении PostgreSQL.
"""

import csv
import io
import os
import sqlite3
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

_pg_conn = None


def _get_conn():
    global _pg_conn
    if DATABASE_URL:
        import psycopg2
        # Переиспользуем соединение если оно живое
        try:
            if _pg_conn and not _pg_conn.closed:
                _pg_conn.cursor().execute("SELECT 1")
                return _pg_conn
        except Exception:
            pass
        _pg_conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return _pg_conn
    return sqlite3.connect("registrations.db")


def _ph():
    return "%s" if DATABASE_URL else "?"


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id            SERIAL PRIMARY KEY,
                telegram_id   BIGINT UNIQUE,
                username      TEXT,
                full_name     TEXT,
                interests     TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                key        TEXT PRIMARY KEY,
                topic      TEXT,
                date       TEXT,
                location   TEXT,
                map        TEXT,
                is_active  BOOLEAN DEFAULT TRUE
            )
        """)
        # Дефолтное событие
        cur.execute("""
            INSERT INTO events (key, topic, date, location, map, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO NOTHING
        """, (
            "current",
            "Claude Code — как создавать приложения и сайты без навыков программирования",
            "16 мая в 14:00",
            "Stockholm Bistro",
            "https://maps.app.goo.gl/usmfZse9BjMYhvEJ6",
            True,
        ))
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id   INTEGER UNIQUE,
                username      TEXT,
                full_name     TEXT,
                interests     TEXT,
                registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                key        TEXT PRIMARY KEY,
                topic      TEXT,
                date       TEXT,
                location   TEXT,
                map        TEXT,
                is_active  INTEGER DEFAULT 1
            )
        """)
        cur.execute("""
            INSERT OR IGNORE INTO events (key, topic, date, location, map, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "current",
            "Claude Code — как создавать приложения и сайты без навыков программирования",
            "16 мая в 14:00",
            "Stockholm Bistro",
            "https://maps.app.goo.gl/usmfZse9BjMYhvEJ6",
            1,
        ))
    conn.commit()
    cur.close() if DATABASE_URL else None


def save_registration(telegram_id, username, full_name, interests):
    ph = _ph()
    conn = _get_conn()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute(f"""
            INSERT INTO registrations (telegram_id, username, full_name, interests)
            VALUES ({ph}, {ph}, {ph}, {ph})
            ON CONFLICT (telegram_id) DO UPDATE SET
                username=EXCLUDED.username,
                full_name=EXCLUDED.full_name,
                interests=EXCLUDED.interests,
                registered_at=CURRENT_TIMESTAMP
        """, (telegram_id, username, full_name, interests))
    else:
        cur.execute(f"""
            INSERT INTO registrations (telegram_id, username, full_name, interests)
            VALUES ({ph}, {ph}, {ph}, {ph})
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                interests=excluded.interests,
                registered_at=CURRENT_TIMESTAMP
        """, (telegram_id, username, full_name, interests))
    conn.commit()
    cur.close() if DATABASE_URL else None


def get_all_registrations():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, username, interests, registered_at "
        "FROM registrations ORDER BY registered_at"
    )
    rows = cur.fetchall()
    cur.close() if DATABASE_URL else None
    result = []
    for row in rows:
        result.append((row[0], row[1], row[2], row[3], str(row[4])[:16]))
    return result


def get_all_telegram_ids():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM registrations")
    ids = [row[0] for row in cur.fetchall()]
    cur.close() if DATABASE_URL else None
    return ids


def get_count():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM registrations")
    count = cur.fetchone()[0]
    cur.close() if DATABASE_URL else None
    return count


def export_csv():
    rows = get_all_registrations()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#", "Имя", "Username", "Интересы", "Дата регистрации"])
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


# ── Событие ───────────────────────────────────────────────────────────────────

def get_event() -> dict:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT topic, date, location, map, is_active FROM events WHERE key=%s" if DATABASE_URL
                else "SELECT topic, date, location, map, is_active FROM events WHERE key=?",
                ("current",))
    row = cur.fetchone()
    cur.close() if DATABASE_URL else None
    if not row:
        return {"topic": "Скоро", "date": "—", "location": "—", "map": "", "is_active": False}
    return {
        "topic":     row[0],
        "date":      row[1],
        "location":  row[2],
        "map":       row[3] or "",
        "is_active": bool(row[4]),
    }


def save_event(topic: str, date: str, location: str, map_url: str):
    ph = _ph()
    conn = _get_conn()
    cur = conn.cursor()
    if DATABASE_URL:
        cur.execute("""
            INSERT INTO events (key, topic, date, location, map, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (key) DO UPDATE SET
                topic=EXCLUDED.topic, date=EXCLUDED.date,
                location=EXCLUDED.location, map=EXCLUDED.map, is_active=TRUE
        """, ("current", topic, date, location, map_url))
    else:
        cur.execute("""
            INSERT INTO events (key, topic, date, location, map, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(key) DO UPDATE SET
                topic=excluded.topic, date=excluded.date,
                location=excluded.location, map=excluded.map, is_active=1
        """, ("current", topic, date, location, map_url))
    conn.commit()
    cur.close() if DATABASE_URL else None


def set_event_active(is_active: bool):
    ph = _ph()
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE events SET is_active={ph} WHERE key={ph}",
        (is_active, "current")
    )
    conn.commit()
    cur.close() if DATABASE_URL else None
