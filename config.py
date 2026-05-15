import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN      = os.getenv("BOT_TOKEN")
ADMIN_ID       = int(os.getenv("ADMIN_ID", "0"))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
COMMUNITY_LINK = os.getenv("COMMUNITY_LINK", "https://t.me/placeholder")

# Информация о мероприятии — менять здесь при смене события
EVENT_TOPIC    = "Claude Code — как создавать приложения и сайты без навыков программирования"
EVENT_DATE     = "16 мая в 14:00"
EVENT_LOCATION = "Stockholm Bistro"
EVENT_MAP      = "https://maps.app.goo.gl/usmfZse9BjMYhvEJ6"
OWNER_USERNAME = "@ildarssagidullin"
