import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
# Супер-админы указываются через запятую в .env
SUPER_ADMIN_IDS = list(map(int, os.getenv("SUPER_ADMIN_IDS", "").split(',')))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file. Make sure it's there.")
if not SUPER_ADMIN_IDS:
    print("Warning: No SUPER_ADMIN_IDS found in .env. Super admin functionality might be limited.")

DATABASE_NAME = "zapster.db"