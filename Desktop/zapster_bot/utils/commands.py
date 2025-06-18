# utils/commands.py
from aiogram import Bot
from aiogram.types import BotCommand

async def set_default_commands(bot: Bot):
    """
    Устанавливает стандартные команды для бота.
    """
    commands = [
        BotCommand(command="start", description="Начать работу с ботом / Перезапустить"),
        BotCommand(command="help", description="Получить помощь"),
        # Добавьте другие команды по необходимости
        # BotCommand(command="admin", description="Панель администратора (для админов)"),
    ]
    await bot.set_my_commands(commands)