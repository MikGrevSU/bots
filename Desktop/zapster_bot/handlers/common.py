from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from config import SUPER_ADMIN_IDS
from db.database import db
from utils.keyboards import get_main_menu_client, get_main_menu_admin, get_main_menu_super_admin

common_router = Router()

async def get_user_role(user_telegram_id: int) -> str:
    """Определяет роль пользователя: 'super_admin', 'location_admin', 'client'."""
    user = await db.get_user_by_telegram_id(user_telegram_id)
    if not user:
        # Если пользователя нет в базе, он регистрируется как клиент.
        # Админы будут добавляться супер-админом.
        user_id = await db.add_user(user_telegram_id)
        user = await db.get_user_by_telegram_id(user_telegram_id) # Получаем полный объект пользователя
        if not user:
            return "unknown" # Не удалось создать пользователя

    admin_info = await db.get_admin_by_user_id(user['user_id'])

    if admin_info:
        return admin_info['role']
    elif user_telegram_id in SUPER_ADMIN_IDS:
        # Если Telegram ID есть в SUPER_ADMIN_IDS, но нет записи в admins,
        # создаем запись супер-админа.
        if not admin_info:
            await db.add_admin(user['user_id'], 'super_admin')
        return 'super_admin'
    else:
        return 'client'


@common_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обрабатывает команду /start.
    Определяет роль пользователя и отправляет соответствующее меню.
    """
    await state.clear() # Сбрасываем все состояния при старте
    
    user_role = await get_user_role(message.from_user.id)
    
    if user_role == 'super_admin':
        await message.answer("Добро пожаловать, Супер-админ!", reply_markup=get_main_menu_super_admin())
    elif user_role == 'location_admin':
        admin_data = await db.get_admin_by_user_id((await db.get_user_by_telegram_id(message.from_user.id))['user_id'])
        location_name = "вашей организации"
        if admin_data and admin_data['location_id']:
            location = await db.get_location_by_id(admin_data['location_id'])
            if location:
                location_name = location['name']
        await message.answer(f"Добро пожаловать, Администратор {location_name}!", reply_markup=get_main_menu_admin())
    else: # client
        await message.answer("Привет! Я бот Zapster, система онлайн-записи. "
                             "Выберите 'Записаться', чтобы начать.", reply_markup=get_main_menu_client())

@common_router.message(F.text == "↩️ Меню клиента")
async def back_to_client_menu(message: types.Message, state: FSMContext):
    """
    Позволяет админам/супер-админам вернуться в меню клиента.
    """
    await state.clear()
    await message.answer("Вы перешли в меню клиента.", reply_markup=get_main_menu_client())