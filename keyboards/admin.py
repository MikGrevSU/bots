# project/keyboards/admin.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
# Импортируем get_all_services, так как она нужна для get_admin_service_selection_keyboard
from db import get_all_services 

def get_admin_main_menu_keyboard():
    """Главное меню админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Просмотр Броней", callback_data="admin_view_bookings"))
    builder.row(InlineKeyboardButton(text="🧰 Управление услугами", callback_data="admin_manage_services"))
    builder.row(InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_view_users"))
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(InlineKeyboardButton(text="📤 Экспорт в Excel", callback_data="admin_export_excel"))
    builder.row(InlineKeyboardButton(text="🚪 Выйти из админ-панели", callback_data="admin_exit"))
    return builder.as_markup()

def get_manage_services_keyboard() -> InlineKeyboardMarkup:
    """Меню управления услугами."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data="admin_add_service"))
    builder.row(InlineKeyboardButton(text="✏️ Редактировать услугу", callback_data="admin_edit_service"))
    builder.row(InlineKeyboardButton(text="👁️ Просмотреть услуги", callback_data="admin_view_services")) # Added this back
    builder.row(InlineKeyboardButton(text="🗑️ Удалить услугу", callback_data="admin_delete_service"))
    builder.row(InlineKeyboardButton(text="↩️ Назад в админ-меню", callback_data="admin_main_menu"))
    return builder.as_markup()

def get_add_service_keyboard():
    """Клавиатура для добавления услуги (например, кнопка Отмена)."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="↩️ Отмена", callback_data="admin_manage_services"))
    return builder.as_markup()

def get_confirm_delete_keyboard(service_id: int): # Добавили service_id для конкретного подтверждения
    """Клавиатура для подтверждения удаления конкретной услуги."""
    builder = InlineKeyboardBuilder()
    # Теперь callback_data включает ID услуги, чтобы знать, что удалять
    builder.row(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_service_{service_id}"))
    builder.row(InlineKeyboardButton(text="❌ Нет, отмена", callback_data="admin_manage_services"))
    return builder.as_markup()

def get_admin_date_selection_keyboard():
    """Клавиатура для выбора даты админом."""
    builder = InlineKeyboardBuilder()
    today = datetime.now().date()
    for i in range(7): # Следующие 7 дней
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        date_display = date.strftime("%d.%m.%Y")
        builder.add(InlineKeyboardButton(text=date_display, callback_data=f"admin_date_{date_str}"))
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="admin_main_menu")) 
    builder.adjust(3) # Adjust to 4 buttons per row for dates
    return builder.as_markup()

def get_admin_service_selection_keyboard(action_prefix: str):
    """
    Клавиатура для выбора услуги админом.
    action_prefix: префикс для callback_data (e.g., 'edit_service_', 'delete_service_')
    """
    services = get_all_services() # Получаем услуги из БД
    if not services:
        return None # Если услуг нет, хендлер должен это обработать

    builder = InlineKeyboardBuilder()
    for service_id, name, price, duration_min in services:
        # Убедитесь, что callback_data генерируется в формате "префикс_ID_услуги"
        builder.row(InlineKeyboardButton(text=f"{name} ({int(price)}₸, {duration_min}мин)", callback_data=f"{action_prefix}{service_id}"))
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="admin_manage_services")) # Возврат в меню управления услугами
    return builder.as_markup()

def get_admin_time_slots_keyboard(time_slots):
    """Клавиатура для выбора времени админом."""
    builder = InlineKeyboardBuilder()
    if not time_slots:
        builder.row(InlineKeyboardButton(text="Нет свободных слотов", callback_data="no_slots"))
    else:
        for slot in time_slots:
            builder.add(InlineKeyboardButton(text=slot, callback_data=f"time_{slot}"))
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_main_menu"))
    builder.adjust(4)
    return builder.as_markup()

# --- КЛАВИАТУРА: Выбор поля для редактирования услуги ---

def get_edit_service_field_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Название", callback_data="edit_service_field_name")
    builder.button(text="Стоимость", callback_data="edit_service_field_price")
    builder.button(text="Длительность", callback_data="edit_service_field_duration_min") # <--- ЭТО ВАЖНО!
    builder.button(text="↩️ Назад", callback_data="admin_main_menu") # Или "admin_manage_services"
    builder.adjust(1) # или 2, как вам удобно
    return builder.as_markup()