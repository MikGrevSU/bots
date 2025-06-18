from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import datetime
from typing import List, Dict, Optional

# --- Основные меню ---

def get_main_menu_client() -> ReplyKeyboardMarkup:
    """Клавиатура для клиента."""
    kb = [
        [KeyboardButton(text="⚡️ Записаться")],
        [KeyboardButton(text="🗓 Мои записи"), KeyboardButton(text="📞 Связь с поддержкой")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)

def get_main_menu_admin() -> ReplyKeyboardMarkup:
    """Клавиатура для админа салона."""
    kb = [
        [KeyboardButton(text="📖 Записи на сегодня")],
        [KeyboardButton(text="⚙️ Управление услугами")],
        [KeyboardButton(text="📊 Статистика по организации")],
        [KeyboardButton(text="↩️ Меню клиента")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)

def get_main_menu_super_admin() -> ReplyKeyboardMarkup:
    """Клавиатура для супер-админа."""
    kb = [
        [KeyboardButton(text="🏢 Управление организациями")],
        [KeyboardButton(text="👨‍💻 Управление админами")],
        [KeyboardButton(text="📈 Глобальная статистика")],
        [KeyboardButton(text="↩️ Меню клиента")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=False)

# --- Клавиатуры для выбора организации/услуги ---

def get_locations_keyboard(locations: List[Dict]) -> InlineKeyboardMarkup:
    """Клавиатура для выбора организации."""
    builder = InlineKeyboardBuilder()
    for loc in locations:
        builder.button(text=loc['name'], callback_data=f"select_location_{loc['location_id']}")
    builder.adjust(1) # По одной кнопке в ряд
    return builder.as_markup()

def get_services_keyboard(services: List[Dict], location_id: int, current_page: int = 0) -> InlineKeyboardMarkup:
    """
    Клавиатура для выбора услуг с пагинацией.
    """
    builder = InlineKeyboardBuilder()
    items_per_page = 5
    start_index = current_page * items_per_page
    end_index = start_index + items_per_page

    for service in services[start_index:end_index]:
        builder.button(
            text=f"{service['name']} ({service['price']} KZT, {service['duration_minutes']} мин)",
            callback_data=f"select_service_{service['service_id']}"
        )
    
    # Кнопки пагинации
    if len(services) > items_per_page:
        nav_buttons = []
        if current_page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"services_page_{location_id}_{current_page - 1}"))
        if end_index < len(services):
            nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"services_page_{location_id}_{current_page + 1}"))
        if nav_buttons:
            builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Назад к организациям", callback_data="back_to_locations"))
    builder.adjust(1)
    return builder.as_markup()


# --- Клавиатуры для выбора даты и времени ---

def get_calendar_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Генерирует инлайн-клавиатуру с календарем."""
    builder = InlineKeyboardBuilder()
    
    # Заголовки дней недели
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    builder.row(*[InlineKeyboardButton(text=day, callback_data="ignore") for day in weekdays])

    # Кнопки для дней
    first_day = datetime.date(year, month, 1)
    # Определяем день недели для первого дня (Пн=0, Вс=6)
    first_weekday = first_day.weekday() 
    
    # Добавляем пустые кнопки для дней до начала месяца
    if first_weekday != 0: # Если месяц начинается не с понедельника
        for _ in range(first_weekday):
            builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))

    # Добавляем дни месяца
    current_day = first_day
    while current_day.month == month:
        if current_day >= datetime.date.today(): # Только будущие или сегодняшние даты
            builder.add(InlineKeyboardButton(text=str(current_day.day), callback_data=f"select_date_{current_day.isoformat()}"))
        else:
            builder.add(InlineKeyboardButton(text=str(current_day.day), callback_data="ignore")) # Неактивные кнопки для прошедших дат
        
        # Переход на новую строку после воскресенья
        if current_day.weekday() == 6:
            builder.row()
        current_day += datetime.timedelta(days=1)
    
    # Кнопки навигации по месяцам
    today = datetime.date.today()
    nav_row = []
    
    prev_month = datetime.date(year, month, 1) - datetime.timedelta(days=1)
    # Разрешаем переходить на прошлые месяцы только если они в будущем относительно текущего
    if prev_month.year > today.year or (prev_month.year == today.year and prev_month.month >= today.month):
        nav_row.append(InlineKeyboardButton(text="<", callback_data=f"calendar_nav_{prev_month.year}_{prev_month.month}"))
    else:
        nav_row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))

    nav_row.append(InlineKeyboardButton(text=f"{first_day.strftime('%B %Y')}", callback_data="ignore"))

    next_month = datetime.date(year, month, 1) + datetime.timedelta(days=32) # Переходим на следующий месяц
    next_month = datetime.date(next_month.year, next_month.month, 1)
    nav_row.append(InlineKeyboardButton(text=">", callback_data=f"calendar_nav_{next_month.year}_{next_month.month}"))
    
    builder.row(*nav_row)
    builder.row(InlineKeyboardButton(text="🔙 Назад к услугам", callback_data="back_to_services"))
    
    return builder.as_markup()

def get_time_slots_keyboard(slots: List[str], selected_date: str) -> InlineKeyboardMarkup:
    """Генерирует инлайн-клавиатуру для выбора времени."""
    builder = InlineKeyboardBuilder()
    
    if not slots:
        builder.button(text="Нет свободных слотов на эту дату 😔", callback_data="ignore_no_slots")
        builder.row(InlineKeyboardButton(text="🔙 Выбрать другую дату", callback_data=f"back_to_date_selection_{selected_date}"))
    else:
        for slot in slots:
            builder.button(text=slot, callback_data=f"select_time_{slot}")
        builder.adjust(3) # 3 кнопки в ряд
        builder.row(InlineKeyboardButton(text="🔙 Выбрать другую дату", callback_data=f"back_to_date_selection_{selected_date}"))

    return builder.as_markup()

# --- Подтверждение / Отмена ---

def get_confirm_booking_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения или отмены записи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"confirm_booking_{booking_id}")
    builder.button(text="❌ Отменить", callback_data=f"cancel_booking_client_{booking_id}")
    return builder.as_markup()

def get_cancel_booking_keyboard(booking_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для отмены записи клиента."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить запись", callback_data=f"cancel_booking_client_{booking_id}")
    return builder.as_markup()

# --- Клавиатуры для админов ---

def get_admin_services_menu() -> InlineKeyboardMarkup:
    """Меню управления услугами для админа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить услугу", callback_data="admin_add_service")
    builder.button(text="📃 Список услуг", callback_data="admin_list_services")
    builder.row(InlineKeyboardButton(text="🔙 В главное меню админа", callback_data="back_to_admin_menu"))
    return builder.as_markup()

def get_admin_service_actions_keyboard(service_id: int) -> InlineKeyboardMarkup:
    """Действия для конкретной услуги (пока только удаление)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑️ Удалить услугу", callback_data=f"admin_delete_service_{service_id}")
    builder.row(InlineKeyboardButton(text="🔙 К списку услуг", callback_data="admin_list_services"))
    return builder.as_markup()


def get_admin_bookings_nav_keyboard(location_id: int, current_date: datetime.date) -> InlineKeyboardMarkup:
    """Навигация по датам для админа при просмотре записей."""
    builder = InlineKeyboardBuilder()
    prev_date = current_date - datetime.timedelta(days=1)
    next_date = current_date + datetime.timedelta(days=1)

    builder.button(text="⬅️ Пред. день", callback_data=f"admin_bookings_date_{prev_date.isoformat()}")
    builder.button(text=f"🗓️ {current_date.strftime('%d.%m.%Y')} 🗓️", callback_data="ignore")
    builder.button(text="След. день ➡️", callback_data=f"admin_bookings_date_{next_date.isoformat()}")
    builder.row(InlineKeyboardButton(text="🔙 В главное меню админа", callback_data="back_to_admin_menu"))
    return builder.as_markup()


# --- Клавиатуры для супер-админа ---

def get_super_admin_locations_menu() -> InlineKeyboardMarkup:
    """Меню управления организациями для супер-админа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить организацию", callback_data="sa_add_location")
    builder.button(text="📃 Список организаций", callback_data="sa_list_locations")
    builder.row(InlineKeyboardButton(text="🔙 В главное меню супер-админа", callback_data="back_to_super_admin_menu"))
    return builder.as_markup()

def get_super_admin_location_details_keyboard(location_id: int) -> InlineKeyboardMarkup:
    """Действия для организации (пока только заглушка)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Удалить организацию (пока не реализовано)", callback_data=f"sa_delete_location_{location_id}")
    builder.row(InlineKeyboardButton(text="🔙 К списку организаций", callback_data="sa_list_locations"))
    return builder.as_markup()

def get_super_admin_admins_menu(locations: List[Dict]) -> InlineKeyboardMarkup:
    """Меню управления админами для супер-админа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить админа", callback_data="sa_add_admin_start")
    builder.button(text="📃 Список админов", callback_data="sa_list_admins")
    builder.row(InlineKeyboardButton(text="🔙 В главное меню супер-админа", callback_data="back_to_super_admin_menu"))
    return builder.as_markup()

def get_super_admin_admin_select_location(locations: List[Dict]) -> InlineKeyboardMarkup:
    """Выбор организации для назначения админа."""
    builder = InlineKeyboardBuilder()
    for loc in locations:
        builder.button(text=loc['name'], callback_data=f"sa_select_admin_location_{loc['location_id']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_super_admin_menu"))
    return builder.as_markup()