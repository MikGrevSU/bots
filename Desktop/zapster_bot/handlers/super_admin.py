from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db.database import db
from utils.keyboards import (
    get_main_menu_super_admin, get_super_admin_locations_menu,
    get_super_admin_location_details_keyboard, get_super_admin_admins_menu,
    get_super_admin_admin_select_location
)

super_admin_router = Router()

# Состояния для супер-админа
class SuperAdminStates(StatesGroup):
    MAIN_MENU = State()
    MANAGE_LOCATIONS = State()
    ADD_LOCATION_NAME = State()
    ADD_LOCATION_ADDRESS = State()
    ADD_LOCATION_DESCRIPTION = State()
    ADD_LOCATION_WORK_HOURS_START = State()
    ADD_LOCATION_WORK_HOURS_END = State()
    ADD_LOCATION_SLOT_DURATION = State()
    
    MANAGE_ADMINS = State()
    ADD_ADMIN_TELEGRAM_ID = State()
    ADD_ADMIN_SELECT_LOCATION = State()


# --- Управление организациями ---

@super_admin_router.message(F.text == "🏢 Управление организациями")
async def manage_locations_menu(message: types.Message, state: FSMContext):
    """Меню управления организациями для супер-админа."""
    await message.answer("Выберите действие:", reply_markup=get_super_admin_locations_menu())
    await state.set_state(SuperAdminStates.MANAGE_LOCATIONS)

@super_admin_router.callback_query(F.data == "sa_add_location", SuperAdminStates.MANAGE_LOCATIONS)
async def sa_add_location_start(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления организации."""
    await callback.message.edit_text("Введите название новой организации:")
    await state.set_state(SuperAdminStates.ADD_LOCATION_NAME)
    await callback.answer()

@super_admin_router.message(SuperAdminStates.ADD_LOCATION_NAME)
async def sa_add_location_name(message: types.Message, state: FSMContext):
    """Получает название организации."""
    await state.update_data(new_location_name=message.text)
    await message.answer("Введите адрес организации:")
    await state.set_state(SuperAdminStates.ADD_LOCATION_ADDRESS)

@super_admin_router.message(SuperAdminStates.ADD_LOCATION_ADDRESS)
async def sa_add_location_address(message: types.Message, state: FSMContext):
    """Получает адрес организации."""
    await state.update_data(new_location_address=message.text)
    await message.answer("Введите краткое описание организации (например, 'Салон красоты с 10-летним опытом'):")
    await state.set_state(SuperAdminStates.ADD_LOCATION_DESCRIPTION)

@super_admin_router.message(SuperAdminStates.ADD_LOCATION_DESCRIPTION)
async def sa_add_location_description(message: types.Message, state: FSMContext):
    """Получает описание организации."""
    await state.update_data(new_location_description=message.text)
    await message.answer("Введите время начала работы (в формате ЧЧ:ММ, например, 09:00):")
    await state.set_state(SuperAdminStates.ADD_LOCATION_WORK_HOURS_START)

@super_admin_router.message(SuperAdminStates.ADD_LOCATION_WORK_HOURS_START)
async def sa_add_location_work_hours_start(message: types.Message, state: FSMContext):
    """Получает время начала работы."""
    if not message.text.match(r"^\d{2}:\d{2}$"):
        await message.answer("Неверный формат. Используйте ЧЧ:ММ (например, 09:00):")
        return
    await state.update_data(new_location_wh_start=message.text)
    await message.answer("Введите время окончания работы (в формате ЧЧ:ММ, например, 18:00):")
    await state.set_state(SuperAdminStates.ADD_LOCATION_WORK_HOURS_END)

@super_admin_router.message(SuperAdminStates.ADD_LOCATION_WORK_HOURS_END)
async def sa_add_location_work_hours_end(message: types.Message, state: FSMContext):
    """Получает время окончания работы."""
    if not message.text.match(r"^\d{2}:\d{2}$"):
        await message.answer("Неверный формат. Используйте ЧЧ:ММ (например, 18:00):")
        return
    await state.update_data(new_location_wh_end=message.text)
    await message.answer("Введите стандартную длительность слота в минутах (например, 30):")
    await state.set_state(SuperAdminStates.ADD_LOCATION_SLOT_DURATION)

@super_admin_router.message(SuperAdminStates.ADD_LOCATION_SLOT_DURATION)
async def sa_add_location_slot_duration(message: types.Message, state: FSMContext):
    """Получает длительность слота и добавляет организацию."""
    try:
        duration = int(message.text)
        if duration <= 0:
            raise ValueError
        
        data = await state.get_data()
        name = data['new_location_name']
        address = data['new_location_address']
        description = data['new_location_description']
        wh_start = data['new_location_wh_start']
        wh_end = data['new_location_wh_end']

        location_id = await db.add_location(name, address, description, wh_start, wh_end, duration)
        if location_id:
            await message.answer(f"✅ Организация '{name}' успешно добавлена!", reply_markup=get_super_admin_locations_menu())
        else:
            await message.answer("❌ Произошла ошибка при добавлении организации.", reply_markup=get_super_admin_locations_menu())
    except ValueError:
        await message.answer("Неверный формат длительности слота. Пожалуйста, введите целое число минут (например, 30):")
    
    await state.set_state(SuperAdminStates.MANAGE_LOCATIONS)


@super_admin_router.callback_query(F.data == "sa_list_locations", SuperAdminStates.MANAGE_LOCATIONS)
async def sa_list_locations(callback: types.CallbackQuery, state: FSMContext):
    """Показывает список всех организаций."""
    locations = await db.get_all_locations()

    if not locations:
        await callback.message.edit_text("Пока нет зарегистрированных организаций.", reply_markup=get_super_admin_locations_menu())
        await callback.answer()
        return

    response_text = "**Список организаций:**\n\n"
    for loc in locations:
        response_text += (
            f"**ID:** `{loc['location_id']}`\n"
            f"**Название:** {loc['name']}\n"
            f"**Адрес:** {loc['address']}\n"
            f"**Рабочие часы:** {loc['working_hours_start']} - {loc['working_hours_end']}\n"
            f"**Длительность слота:** {loc['slot_duration_minutes']} мин\n\n"
        )
        # Отправляем каждую организацию отдельно с опциональными кнопками действий
        await callback.message.answer(
            response_text,
            reply_markup=get_super_admin_location_details_keyboard(loc['location_id']) # Пока заглушка
        )
        response_text = "" # Сбрасываем для следующей итерации
    
    if not response_text: # Если все были отправлены по одной
        await callback.message.answer("⬆️ Это все зарегистрированные организации.", reply_markup=get_super_admin_locations_menu())

    await state.set_state(SuperAdminStates.MANAGE_LOCATIONS)
    await callback.answer()

# --- Управление админами ---

@super_admin_router.message(F.text == "👨‍💻 Управление админами")
async def manage_admins_menu(message: types.Message, state: FSMContext):
    """Меню управления админами для супер-админа."""
    locations = await db.get_all_locations()
    await message.answer("Выберите действие:", reply_markup=get_super_admin_admins_menu(locations))
    await state.set_state(SuperAdminStates.MANAGE_ADMINS)

@super_admin_router.callback_query(F.data == "sa_add_admin_start", SuperAdminStates.MANAGE_ADMINS)
async def sa_add_admin_start(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс добавления админа."""
    await callback.message.edit_text("Введите Telegram ID пользователя, которого хотите назначить админом (числовой ID):")
    await state.set_state(SuperAdminStates.ADD_ADMIN_TELEGRAM_ID)
    await callback.answer()

@super_admin_router.message(SuperAdminStates.ADD_ADMIN_TELEGRAM_ID)
async def sa_add_admin_telegram_id(message: types.Message, state: FSMContext):
    """Получает Telegram ID нового админа и предлагает выбрать организацию."""
    try:
        tg_id = int(message.text)
        # Проверяем, существует ли пользователь в нашей базе, если нет - создаем
        user = await db.get_user_by_telegram_id(tg_id)
        if not user:
            user_id = await db.add_user(tg_id)
            if not user_id:
                await message.answer("Ошибка при создании пользователя. Попробуйте еще раз.")
                await message.answer("Выберите действие:", reply_markup=get_super_admin_admins_menu(await db.get_all_locations()))
                await state.set_state(SuperAdminStates.MANAGE_ADMINS)
                return
            user = {'user_id': user_id, 'telegram_id': tg_id} # Создаем фиктивный объект для продолжения
        
        # Проверяем, не является ли он уже админом
        existing_admin = await db.get_admin_by_user_id(user['user_id'])
        if existing_admin:
            await message.answer(f"Пользователь с Telegram ID `{tg_id}` уже является админом (Роль: {existing_admin['role']}).")
            await message.answer("Выберите действие:", reply_markup=get_super_admin_admins_menu(await db.get_all_locations()))
            await state.set_state(SuperAdminStates.MANAGE_ADMINS)
            return

        await state.update_data(new_admin_user_id=user['user_id'], new_admin_telegram_id=tg_id)

        locations = await db.get_all_locations()
        if not locations:
            await message.answer("Нет организаций для привязки админа. Сначала добавьте организации.", reply_markup=get_super_admin_admins_menu(locations))
            await state.set_state(SuperAdminStates.MANAGE_ADMINS)
            return

        await message.answer(
            f"Пользователь с Telegram ID `{tg_id}` будет назначен админом.\n"
            "Выберите организацию, которой он будет управлять:",
            reply_markup=get_super_admin_admin_select_location(locations)
        )
        await state.set_state(SuperAdminStates.ADD_ADMIN_SELECT_LOCATION)

    except ValueError:
        await message.answer("Неверный формат Telegram ID. Пожалуйста, введите целое число:")

@super_admin_router.callback_query(F.data.startswith("sa_select_admin_location_"), SuperAdminStates.ADD_ADMIN_SELECT_LOCATION)
async def sa_add_admin_select_location(callback: types.CallbackQuery, state: FSMContext):
    """Привязывает нового админа к выбранной организации."""
    location_id = int(callback.data.split("_")[4])
    data = await state.get_data()
    user_id = data['new_admin_user_id']
    tg_id = data['new_admin_telegram_id']

    admin_id = await db.add_admin(user_id, 'location_admin', location_id)
    location = await db.get_location_by_id(location_id)

    if admin_id:
        await callback.message.edit_text(
            f"✅ Пользователь с Telegram ID `{tg_id}` успешно назначен админом для организации '{location['name']}'."
        )
    else:
        await callback.message.edit_text("❌ Произошла ошибка при добавлении админа.")
    
    await callback.message.answer("Выберите действие:", reply_markup=get_super_admin_admins_menu(await db.get_all_locations()))
    await state.set_state(SuperAdminStates.MANAGE_ADMINS)
    await callback.answer()


@super_admin_router.callback_query(F.data == "sa_list_admins", SuperAdminStates.MANAGE_ADMINS)
async def sa_list_admins(callback: types.CallbackQuery, state: FSMContext):
    """Показывает список всех админов."""
    admins = await db.get_all_admins()

    if not admins:
        await callback.message.edit_text("Пока нет зарегистрированных админов (кроме вас, если вы супер-админ).", reply_markup=get_super_admin_admins_menu(await db.get_all_locations()))
        await callback.answer()
        return

    response_text = "**Список зарегистрированных админов:**\n\n"
    for admin in admins:
        location_name = admin.get('location_name', 'Не привязана')
        if admin['role'] == 'super_admin':
            location_name = "Все организации (Супер-админ)"

        response_text += (
            f"**ID Админа:** `{admin['admin_id']}`\n"
            f"**Telegram ID:** `{admin['telegram_id']}`\n"
            f"**Роль:** {admin['role']}\n"
            f"**Организация:** {location_name}\n\n"
        )
    
    await callback.message.edit_text(response_text, reply_markup=get_super_admin_admins_menu(await db.get_all_locations()))
    await state.set_state(SuperAdminStates.MANAGE_ADMINS)
    await callback.answer()


@super_admin_router.callback_query(F.data == "back_to_super_admin_menu")
async def back_to_super_admin_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню супер-админа."""
    await callback.message.edit_text("Добро пожаловать, Супер-админ!", reply_markup=get_main_menu_super_admin())
    await state.clear()
    await callback.answer()

# --- Глобальная статистика (MVP: заглушка) ---
@super_admin_router.message(F.text == "📈 Глобальная статистика")
async def global_statistics(message: types.Message, state: FSMContext):
    """Показывает глобальную статистику."""
    locations = await db.get_all_locations()
    total_locations = len(locations)
    all_admins = await db.get_all_admins()
    total_admins = len(all_admins) # Считая супер-админов

    # Для MVP, просто заглушка
    await message.answer(
        f"**📈 Глобальная статистика Zapster**\n\n"
        f"**Всего организаций:** {total_locations}\n"
        f"**Всего админов:** {total_admins}\n"
        "*(Детальная глобальная статистика будет доступна в будущих версиях)*",
        reply_markup=get_main_menu_super_admin()
    )
    await state.clear()


# --- Управление всеми записями (MVP: заглушка) ---
@super_admin_router.message(F.text == "Управление записями") # Этой кнопки пока нет в меню, но если добавить
async def manage_all_bookings(message: types.Message, state: FSMContext):
    """Показывает заглушку для управления всеми записями."""
    await message.answer(
        "Функционал полного контроля над всеми записями "
        "для супер-админа будет реализован в следующих версиях.",
        reply_markup=get_main_menu_super_admin()
    )
    await state.clear()