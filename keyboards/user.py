# project/keyboards/user.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from datetime import date, datetime, timedelta
from typing import List, Tuple
# Don't forget to import ADMIN_IDS from your config file
from config import ADMIN_IDS 


def get_phone_request_keyboard():
    """Клавиатура для запроса номера телефона."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    """
    Основное меню пользователя.
    Добавляет кнопку "Админ-панель", если пользователь является администратором.
    """
    # Define the base keyboard layout
    keyboard_layout = [
        [KeyboardButton(text="✍️ Записаться на услугу")],
        [KeyboardButton(text="🗓️ Мои записи"), KeyboardButton(text="📜 История записей")],
        [KeyboardButton(text="✉️ Сообщить об опоздании")]
    ]

    # Check if the user is an admin and append the admin button
    if user_id in ADMIN_IDS:
        # Use ReplyKeyboardMarkup for adding the button, no callback_data needed here
        # The admin command will be handled by handlers/admin.py
        keyboard_layout.append([KeyboardButton(text="⚙️ Админ-панель")])

    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_layout,
        resize_keyboard=True
    )
    return keyboard

def get_cancel_keyboard():
    """Клавиатура с кнопкой отмены."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

def get_services_keyboard(services: list):
    """Генерирует инлайн-клавиатуру со списком услуг."""
    builder = InlineKeyboardBuilder()
    for service_id, name, price, duration_min in services:
        # Изменяем форматирование цены: добавляем "₸"
        builder.button(text=f"{name} ({int(price)} ₸)", callback_data=f"service_{service_id}")
    builder.adjust(1) # По одной кнопке в ряд
    return builder.as_markup()

def get_confirmation_keyboard():
    """Генерирует инлайн-клавиатуру для подтверждения или отмены записи."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить запись", callback_data="confirm_booking"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking_process") # Новая callback_data для отмены всего процесса
    )
    return builder.as_markup()

def get_dates_keyboard():
    """Генерирует инлайн-клавиатуру с датами на ближайшие 7 дней и кнопкой "Назад"."""
    builder = InlineKeyboardBuilder()
    today = datetime.now().date()
    for i in range(7):
        date = today + timedelta(days=i)
        builder.button(text=date.strftime("%d.%m"), callback_data=f"date_{date.strftime('%Y-%m-%d')}")
    builder.adjust(3) # Например, 4 кнопки в ряд для дат

    # Добавляем кнопку "Назад" к выбору услуги
    builder.row(InlineKeyboardButton(text="⬅️ Назад к выбору услуги", callback_data="back_to_service_selection"))
    return builder.as_markup()

def get_time_slots_keyboard(time_slots: list):
    """Генерирует инлайн-клавиатуру с доступными временными слотами и кнопкой "Назад"."""
    builder = InlineKeyboardBuilder()
    if not time_slots:
        builder.button(text="Нет свободных слотов на эту дату", callback_data="no_slots")
        builder.adjust(1)
    else:
        for slot in time_slots:
            builder.button(text=slot, callback_data=f"time_{slot}")
        builder.adjust(3) # Можно регулировать количество кнопок в ряду

    # Добавляем кнопку "Назад"
    builder.row(InlineKeyboardButton(text="⬅️ Назад к выбору даты", callback_data="back_to_date_selection"))
    return builder.as_markup()

def get_booking_action_keyboard(booking_id: int):
    """Клавиатура для управления активной бронью (отмена)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить запись", callback_data=f"cancel_booking_{booking_id}")
    return builder.as_markup()

def get_confirm_cancel_keyboard(booking_id: int):
    """Клавиатура для подтверждения отмены брони."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, отменить", callback_data=f"confirm_cancel_{booking_id}")
    builder.button(text="⬅️ Назад", callback_data="back_to_my_bookings")
    return builder.as_markup()