import sqlite3
import csv
import io

DB_PATH = "registrations.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
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
    conn.close()


def save_registration(telegram_id, username, full_name, interests):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO registrations (telegram_id, username, full_name, interests)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name,
            interests=excluded.interests,
            registered_at=CURRENT_TIMESTAMP
    """, (telegram_id, username, full_name, interests))
    conn.commit()
    conn.close()


def get_all_registrations():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, full_name, username, interests, registered_at "
        "FROM registrations ORDER BY registered_at"
    ).fetchall()
    conn.close()
    return rows


def get_count():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    conn.close()
    return count


def get_all_telegram_ids():
    conn = sqlite3.connect(DB_PATH)
    ids = [row[0] for row in conn.execute("SELECT telegram_id FROM registrations").fetchall()]
    conn.close()
    return ids


def export_csv():
    rows = get_all_registrations()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#", "Имя", "Username", "Интересы", "Дата регистрации"])
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")  # utf-8-sig — Excel открывает без кракозябр
