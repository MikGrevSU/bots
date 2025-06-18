import asyncio
import logging
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

# Теперь db импортируется как экземпляр, и у него есть методы init_db() и close()
from db.database import db # Это наш экземпляр DBManager
from handlers import common, client, admin, super_admin # Импортируем все роутеры
from middlewares.register_check import RegisterCheck # Теперь RegisterCheck ожидает db_manager
from utils.commands import set_default_commands

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting Zapster Bot...")

    # Инициализация базы данных
    await db.init_db()
    logger.info("Database initialized successfully.")

    # Получение токена бота из переменных окружения
    BOT_TOKEN = getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set.")
        exit(1)

    # Инициализация хранилища состояний (для FSM)
    storage = MemoryStorage()

    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='Markdown'))
    dp = Dispatcher(storage=storage)

    # Регистрация роутеров
    dp.include_router(common.common_router)
    dp.include_router(client.client_router)
    dp.include_router(admin.admin_router)
    dp.include_router(super_admin.super_admin_router)

    # Регистрация мидлварей
    # <--- ВОТ ЭТОТ БЛОК НУЖНО ИЗМЕНИТЬ!
    # Теперь RegisterCheck ожидает аргумент db_manager.
    # Мы передаем наш глобальный экземпляр 'db'
    dp.message.middleware(RegisterCheck(db_manager=db))
    dp.callback_query.middleware(RegisterCheck(db_manager=db))
    # --->

    # Установка команд бота
    await set_default_commands(bot)
    logger.info("Default commands set.")

    # Запуск бота
    logger.info("Bot started successfully. Polling for updates...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually by user.")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        # Важно: всегда закрывайте соединение с базой данных при завершении работы бота.
        if db.conn: # Проверяем, что соединение вообще было установлено
            asyncio.run(db.close())
            logger.info("Database connection closed.")