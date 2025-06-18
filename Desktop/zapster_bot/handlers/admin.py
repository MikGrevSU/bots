from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import datetime

from db.database import db
from utils.keyboards import get_main_menu_admin, get_admin_services_menu, get_admin_service_actions_keyboard, get_admin_bookings_nav_keyboard

admin_router = Router()

# Состояния для админа
class AdminStates(StatesGroup):
    MAIN_MENU = State()
    VIEWING_BOOKINGS = State()
    MANAGE_SERVICES = State()
    ADD_SERVICE_NAME = State()
    ADD_SERVICE_PRICE = State()
    ADD_SERVICE_DURATION = State()
    DELETE_SERVICE_CONFIRM = State()


# --- Просмотр записей ---

@admin_router.message(F.text == "📖 Записи на сегодня")
async def view_today_bookings(message: types.Message, state: FSMContext):
    """Показывает записи для организации админа на сегодня."""
    user = await db.get_user_by_telegram_id(message.from_user.id)
    admin_data = await db.get_admin_by_user_id(user['user_id'])
    
    if not admin_data or not admin_data['location_id']:
        await message.answer("Вы не привязаны ни к одной организации.")
        return

    location_id = admin_data['location_id']
    today_date = datetime.date.today()

    await state.update_data(current_admin_location_id=location_id)
    await show_bookings_for_date(message, state, location_id, today_date)


@admin_router.callback_query(F.data.startswith("admin_bookings_date_"))
async def admin_bookings_date_nav(callback: types.CallbackQuery, state: FSMContext):
    """Навигация по датам для админа при просмотре записей."""
    selected_date_str = callback.data.split("_")[3]
    selected_date = datetime.date.fromisoformat(selected_date_str)

    data = await state.get_data()
    location_id = data.get('current_admin_location_id')
    if not location_id:
        await callback.message.edit_text("Ошибка: Не удалось определить организацию.")
        await state.clear()
        return

    await show_bookings_for_date(callback.message, state, location_id, selected_date, edit_message=True)
    await callback.answer()


async def show_bookings_for_date(message: types.Message, state: FSMContext, location_id: int, date: datetime.date, edit_message: bool = False):
    """Вспомогательная функция для отображения записей на дату."""
    bookings = await db.get_location_bookings_for_date(location_id, date.isoformat())
    location = await db.get_location_by_id(location_id)

    header_text = f"**Записи на {date.strftime('%d.%m.%Y')} для {location['name']}:**\n\n"
    response_text = ""

    if not bookings:
        response_text = "Нет записей на эту дату."
    else:
        for i, booking in enumerate(bookings):
            response_text += (
                f"{i+1}. **Время:** {booking['booking_time']}\n"
                f"   **Услуга:** {booking['service_name']}\n"
                f"   **Клиент:** `{booking['phone_number']}` (Telegram ID: `{booking['user_id']}`)\n\n"
            )
    
    if edit_message:
        await message.edit_text(
            header_text + response_text,
            reply_markup=get_admin_bookings_nav_keyboard(location_id, date),
            parse_mode='Markdown'
        )
    else:
        await message.answer(
            header_text + response_text,
            reply_markup=get_admin_bookings_nav_keyboard(location_id, date),
            parse_mode='Markdown'
        )
    await state.set_state(AdminStates.VIEWING_BOOKINGS)

# --- Управление услугами ---

@admin_router.message(F.text == "⚙️ Управление услугами")
async def manage_services_menu(message: types.Message, state: FSMContext):
    """Показывает меню управления услугами."""
    user = await db.get_user_by_telegram_id(message.from_user.id)
    admin_data = await db.get_admin_by_user_id(user['user_id'])
    
    if not admin_data or not admin_data['location_id']:
        await message.answer("Вы не привязаны ни к одной организации.")
        return
    
    await state.update_data(current_admin_location_id=admin_data['location_id'])
    await message.answer("Выберите действие:", reply_markup=get_admin_services_menu())
    await state.set_state(AdminStates.MANAGE_SERVICES)

@admin_router.callback_query(F.data == "admin_add_service", AdminStates.MANAGE_SERVICES)
async def admin_add_service_start(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления услуги."""
    await callback.message.edit_text("Введите название новой услуги:")
    await state.set_state(AdminStates.ADD_SERVICE_NAME)
    await callback.answer()

@admin_router.message(AdminStates.ADD_SERVICE_NAME)
async def admin_add_service_name(message: types.Message, state: FSMContext):
    """Получает название услуги."""
    await state.update_data(new_service_name=message.text)
    await message.answer("Теперь введите цену услуги (например, 1500.00):")
    await state.set_state(AdminStates.ADD_SERVICE_PRICE)

@admin_router.message(AdminStates.ADD_SERVICE_PRICE)
async def admin_add_service_price(message: types.Message, state: FSMContext):
    """Получает цену услуги."""
    try:
        price = float(message.text.replace(',', '.'))
        await state.update_data(new_service_price=price)
        await message.answer("Теперь введите длительность услуги в минутах (например, 60):")
        await state.set_state(AdminStates.ADD_SERVICE_DURATION)
    except ValueError:
        await message.answer("Неверный формат цены. Пожалуйста, введите число (например, 1500 или 1500.50):")

@admin_router.message(AdminStates.ADD_SERVICE_DURATION)
async def admin_add_service_duration(message: types.Message, state: FSMContext):
    """Получает длительность услуги и добавляет ее."""
    try:
        duration = int(message.text)
        if duration <= 0:
            raise ValueError
        
        data = await state.get_data()
        location_id = data['current_admin_location_id']
        name = data['new_service_name']
        price = data['new_service_price']

        service_id = await db.add_service(location_id, name, price, duration)
        if service_id:
            await message.answer(f"✅ Услуга '{name}' успешно добавлена!", reply_markup=get_admin_services_menu())
        else:
            await message.answer("❌ Произошла ошибка при добавлении услуги.", reply_markup=get_admin_services_menu())
    except ValueError:
        await message.answer("Неверный формат длительности. Пожалуйста, введите целое число минут (например, 60):")
    
    await state.set_state(AdminStates.MANAGE_SERVICES)


@admin_router.callback_query(F.data == "admin_list_services", AdminStates.MANAGE_SERVICES)
async def admin_list_services(callback: types.CallbackQuery, state: FSMContext):
    """Показывает список услуг организации."""
    data = await state.get_data()
    location_id = data['current_admin_location_id']
    services = await db.get_services_by_location(location_id)

    if not services:
        await callback.message.edit_text("В вашей организации пока нет услуг.", reply_markup=get_admin_services_menu())
        await callback.answer()
        return

    response_text = "**Список ваших услуг:**\n\n"
    for service in services:
        response_text += (
            f"**ID:** `{service['service_id']}`\n"
            f"**Название:** {service['name']}\n"
            f"**Цена:** {service['price']} KZT\n"
            f"**Длительность:** {service['duration_minutes']} мин\n\n"
        )
        await callback.message.answer(
            response_text,
            reply_markup=get_admin_service_actions_keyboard(service['service_id'])
        )
        response_text = "" # Сбрасываем для следующей итерации
    
    if not response_text: # Если все были отправлены по одной
         await callback.message.answer("⬆️ Это все ваши услуги.", reply_markup=get_admin_services_menu())

    await state.set_state(AdminStates.MANAGE_SERVICES)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_delete_service_"), AdminStates.MANAGE_SERVICES)
async def admin_delete_service(callback: types.CallbackQuery, state: FSMContext):
    """Удаляет услугу."""
    service_id = int(callback.data.split("_")[3])
    
    # Проверка, что услуга принадлежит этой организации
    service = await db.get_service_by_id(service_id)
    data = await state.get_data()
    location_id = data['current_admin_location_id']

    if not service or service['location_id'] != location_id:
        await callback.answer("Эта услуга не принадлежит вашей организации.", show_alert=True)
        await callback.message.edit_text("Не удалось удалить услугу.", reply_markup=get_admin_services_menu())
        return

    success = await db.delete_service(service_id)
    if success:
        await callback.message.edit_text(f"✅ Услуга '{service['name']}' успешно удалена.")
    else:
        await callback.message.edit_text("❌ Произошла ошибка при удалении услуги.")
    
    await callback.message.answer("Выберите действие:", reply_markup=get_admin_services_menu())
    await callback.answer()

@admin_router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню админа."""
    await callback.message.edit_text("Добро пожаловать, Администратор!", reply_markup=get_main_menu_admin())
    await state.clear()
    await callback.answer()

# --- Статистика по организации (MVP: заглушка) ---
@admin_router.message(F.text == "📊 Статистика по организации")
async def org_statistics(message: types.Message, state: FSMContext):
    """Показывает базовую статистику по организации."""
    user = await db.get_user_by_telegram_id(message.from_user.id)
    admin_data = await db.get_admin_by_user_id(user['user_id'])
    
    if not admin_data or not admin_data['location_id']:
        await message.answer("Вы не привязаны ни к одной организации.")
        return

    location_id = admin_data['location_id']
    location = await db.get_location_by_id(location_id)

    # Для MVP, просто заглушка
    today_bookings = await db.get_location_bookings_for_date(location_id, datetime.date.today().isoformat())
    
    await message.answer(
        f"**📊 Статистика по организации: {location['name']}**\n\n"
        f"**Записей на сегодня:** {len(today_bookings)}\n"
        "*(Расширенная статистика будет доступна в будущих версиях)*",
        reply_markup=get_main_menu_admin()
    )
    await state.clear()