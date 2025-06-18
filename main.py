# project/main.py
import asyncio
import logging
from datetime import datetime, timedelta # Убедитесь, что это импортировано

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from handlers.user import user_router
from handlers.admin import admin_router # <--- Важно: импортируем админ-роутер
from db import init_db, get_bookings_for_notification, mark_booking_notified, get_user

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Фоновая задача для напоминаний (оставьте как есть, она уже работает) ---
async def send_reminders(bot: Bot):
    REMINDER_CHECK_INTERVAL_SECONDS = 60
    REMINDER_TIME_MINUTES = 30
    
    logger.info("Фоновая задача отправки напоминаний запущена.")

    while True:
        try:
            bookings_to_notify = get_bookings_for_notification(REMINDER_TIME_MINUTES)
            
            for booking_id, user_tg_id, service_name, booking_date_str, booking_time_str in bookings_to_notify:
                user_info = get_user(user_tg_id)
                if not user_info:
                    logger.warning(f"Пользователь {user_tg_id} не найден для записи {booking_id}. Пропускаем уведомление.")
                    mark_booking_notified(booking_id)
                    continue

                notification_text = (
                    f"⏰ Напоминание о предстоящей записи! ⏰\n\n"
                    f"Услуга: <b>{service_name}</b>\n"
                    f"Дата: <b>{datetime.strptime(booking_date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
                    f"Время: <b>{booking_time_str}</b>\n\n"
                    f"Ждем вас!"
                )
                
                try:
                    await bot.send_message(chat_id=user_tg_id, text=notification_text, parse_mode=ParseMode.HTML)
                    mark_booking_notified(booking_id)
                    logger.info(f"Напоминание отправлено пользователю {user_tg_id} для записи {booking_id}")
                except Exception as e:
                    logger.error(f"Ошибка при отправке напоминания пользователю {user_tg_id} для записи {booking_id}: {e}")
                    mark_booking_notified(booking_id) # Все равно помечаем, чтобы не спамить, если ошибка повторяющаяся
            
        except Exception as e:
            logger.error(f"Критическая ошибка в фоновой задаче отправки напоминаний: {e}")
        
        await asyncio.sleep(REMINDER_CHECK_INTERVAL_SECONDS)

async def main():
    init_db()

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден в .env файле. Убедитесь, что он установлен.")
        return

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_router(admin_router)
    dp.include_router(user_router)
     # <--- Важно: регистрируем админ-роутер

    logger.info("Бот запущен. Нажмите Ctrl+C для остановки.")
    
    asyncio.create_task(send_reminders(bot)) 

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())