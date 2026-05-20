"""
База данных: MongoDB Atlas (постоянное хранение).
Подключение через MONGO_URL в .env / Railway Variables.
"""

import csv
import io
import os
from datetime import datetime, timezone

from pymongo import MongoClient

MONGO_URL = os.getenv("MONGO_URL", "")
_client = None
_db = None

# ── Подключение ───────────────────────────────────────────────────────────────

def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(
            MONGO_URL,
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=10000,
        )
        _db = _client["aiclub"]
    return _db


def init_db():
    """Создаёт индексы и начальное событие если их нет."""
    db = _get_db()
    db["registrations"].create_index("telegram_id", unique=True)
    # Создаём событие по умолчанию если база пустая
    if db["events"].count_documents({"_id": "current"}) == 0:
        db["events"].insert_one({
            "_id": "current",
            "topic": "Claude Code — как создавать приложения и сайты без навыков программирования",
            "date": "16 мая в 14:00",
            "location": "Stockholm Bistro",
            "map": "https://maps.app.goo.gl/usmfZse9BjMYhvEJ6",
            "is_active": True,
        })


# ── Регистрации ───────────────────────────────────────────────────────────────

def save_registration(telegram_id, username, full_name, interests):
    db = _get_db()
    db["registrations"].update_one(
        {"telegram_id": telegram_id},
        {"$set": {
            "telegram_id": telegram_id,
            "username": username,
            "full_name": full_name,
            "interests": interests,
            "registered_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


def get_all_registrations():
    db = _get_db()
    docs = list(db["registrations"].find({}, {"_id": 0}).sort("registered_at", 1))
    result = []
    for i, d in enumerate(docs, 1):
        result.append((
            i,
            d.get("full_name", ""),
            d.get("username", ""),
            d.get("interests", ""),
            str(d.get("registered_at", ""))[:16],
        ))
    return result


def get_all_telegram_ids():
    db = _get_db()
    return [d["telegram_id"] for d in db["registrations"].find({}, {"telegram_id": 1})]


def get_count():
    return _get_db()["registrations"].count_documents({})


def export_csv():
    rows = get_all_registrations()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["#", "Имя", "Username", "Интересы", "Дата регистрации"])
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


# ── Событие (анонс встречи) ───────────────────────────────────────────────────

def get_event() -> dict:
    """Возвращает текущее событие из БД."""
    doc = _get_db()["events"].find_one({"_id": "current"})
    if not doc:
        return {
            "topic": "Скоро — следи за анонсами",
            "date": "—",
            "location": "—",
            "map": "",
            "is_active": False,
        }
    return doc


def save_event(topic: str, date: str, location: str, map_url: str):
    """Сохраняет новый анонс встречи."""
    _get_db()["events"].update_one(
        {"_id": "current"},
        {"$set": {
            "topic": topic,
            "date": date,
            "location": location,
            "map": map_url,
            "is_active": True,
        }},
        upsert=True,
    )


def set_event_active(is_active: bool):
    """Включает / выключает отображение анонса."""
    _get_db()["events"].update_one(
        {"_id": "current"},
        {"$set": {"is_active": is_active}},
    )
