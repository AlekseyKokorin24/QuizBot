import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "quizbot.sqlite3")

# Настройки игры (по умолчанию)
QUIZ_INTERVAL_HOURS = int(os.getenv("QUIZ_INTERVAL_HOURS", "2"))
QUIZ_WINDOW_SECONDS = int(os.getenv("QUIZ_WINDOW_SECONDS", "180"))  # 3 минуты
POINTS_PER_CORRECT = int(os.getenv("POINTS_PER_CORRECT", "10"))

# Для админских команд можно ограничить список админов по user_id, если хочешь
ADMIN_IDS = set(int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit())


