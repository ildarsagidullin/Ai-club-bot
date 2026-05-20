import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN      = os.getenv("BOT_TOKEN")
ADMIN_ID       = int(os.getenv("ADMIN_ID", "0"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
COMMUNITY_LINK = os.getenv("COMMUNITY_LINK", "https://t.me/aiclubcom")

# Контакт организатора (не меняется)
OWNER_USERNAME = "@ildarssagidullin"

# Событие теперь хранится в MongoDB (database.get_event())
# config.py больше не содержит EVENT_TOPIC, EVENT_DATE и т.д.
