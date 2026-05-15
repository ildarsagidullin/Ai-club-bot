"""
База данных: PostgreSQL на Railway, SQLite локально.
Railway автоматически добавляет DATABASE_URL при подключении PostgreSQL.
"""

import csv
import io
import os
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL")  # есть на Railway, нет локально

# ── Подключение ───────────────────────────────────────────────────────────────

def _get_conn():
    if DATABASE_URL:
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    return sqlite3.connect("registrations.db")


def _ph():
    """Placeholder: %s для PostgreSQL, ? для SQLite."""
    return "%s" if DATABASE_URL else "?"


# ── Инициализация ─────────────────────────────────────────────────────────────

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
    conn.commit()
    cur.close()
    conn.close()


# ── Сохранить регистрацию ─────────────────────────────────────────────────────

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
    cur.close()
    conn.close()


# ── Получить всех ─────────────────────────────────────────────────────────────

def get_all_registrations():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, username, interests, registered_at "
        "FROM registrations ORDER BY registered_at"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def get_all_telegram_ids():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT telegram_id FROM registrations")
    ids = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return ids


def get_count():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM registrations")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


# ── Экспорт CSV ───────────────────────────────────────────────────────────────

def export_csv():
    rows = get_all_registrations()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#", "Имя", "Username", "Интересы", "Дата регистрации"])
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")
