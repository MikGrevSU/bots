from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
# Убираем прямой импорт 'db', вместо этого будем передавать его через __init__
# from db.database import db 

class RegisterCheck(BaseMiddleware):
    # Теперь миддлварь принимает экземпляр DBManager при инициализации
    def __init__(self, db_manager):
        self.db_manager = db_manager

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery, # Может быть Message или CallbackQuery
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        username = event.from_user.username
        full_name = event.from_user.full_name

        # Проверяем, существует ли пользователь в базе данных, используя переданный db_manager
        user = await self.db_manager.get_user_by_telegram_id(user_id)

        if not user:
            # Если пользователя нет, регистрируем его
            # Вызываем add_user с user_id, username и full_name.
            # phone_number будет None, если не передан.
            await self.db_manager.add_user(user_id, username, full_name)
            
            # Отправляем приветственное сообщение
            if isinstance(event, Message):
                await event.answer("Добро пожаловать! Вы успешно зарегистрированы. Используйте главное меню.")
            elif isinstance(event, CallbackQuery):
                await event.message.answer("Добро пожаловать! Вы успешно зарегистрированы. Используйте главное меню.")

        # Передаем управление следующему обработчику или миддлвари
        return await handler(event, data)