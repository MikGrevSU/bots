# project/handlers/admin.py

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter 
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
from aiogram.exceptions import TelegramBadRequest
from typing import Union

from config import ADMIN_IDS
from db import (
    get_all_bookings_for_date, get_all_bookings_in_system, add_service,
    get_all_services, delete_service, create_booking,
    cancel_booking, get_service, update_service, get_all_users
)
from keyboards.admin import (
    get_admin_main_menu_keyboard, get_manage_services_keyboard,
    get_confirm_delete_keyboard,
    get_admin_date_selection_keyboard, get_admin_service_selection_keyboard,
    get_edit_service_field_keyboard, get_add_service_keyboard
)
from keyboards.user import get_main_menu_keyboard # <-- Убедитесь, что эта функция здесь

admin_router = Router()
logger = logging.getLogger(__name__)

# --- Определение состояний для админ-панели ---
class AdminStates(StatesGroup):
    admin_menu = State()

    # Просмотр броней
    view_bookings_select_date = State()

    # Удаление брони
    delete_booking_enter_id = State()

    # Управление услугами
    manage_services_menu = State()
    add_service_name = State()
    add_service_price = State()
    add_service_duration = State()

    # Редактирование услуг
    edit_service_select = State()
    edit_service_field = State()
    edit_service_enter_new_value = State()

    # Удаление услуги
    delete_service_select = State()
    delete_service_confirm = State()

    # Просмотр пользователей
    view_users = State()

    # Статистика и экспорт
    stats_menu = State()
    export_excel_menu = State()

# --- Вспомогательная функция для отображения названий полей ---
def field_to_edit_display_name(field_name):
    display_names = {
        "name": "Название",
        "price": "Стоимость",
        "duration_min": "Длительность"
    }
    return display_names.get(field_name, field_name)

# --- Вход в админ-панель ---
@admin_router.message(Command("admin")) # Отдельный хендлер для команды /admin
@admin_router.message(F.text == "⚙️ Админ-панель") # Отдельный хендлер для кнопки "Админ-панель"
async def cmd_admin(message: Message, state: FSMContext):
    if message.from_user.id in ADMIN_IDS:
        logger.info(f"Администратор {message.from_user.id} вошел в админ-панель.")
        # Отправляем сообщение с админской inline-клавиатурой
        # и удаляем текущую Reply-клавиатуру
        await message.answer(
            "Добро пожаловать в админ-панель!",
            reply_markup=get_admin_main_menu_keyboard() # Админская Inline-клавиатура
        )
        await message.answer(
            "Админ панель.", # Или " " (пробел), но "Меню обновлено." надежнее
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(AdminStates.admin_menu)
    else:
        logger.warning(f"Несанкционированная попытка доступа к админ-панели от пользователя {message.from_user.id}.")
        await message.answer("У вас нет доступа к админ-панели.")

# --- ХЕНДЛЕР ГЛАВНОГО АДМИН-МЕНЮ (ОТВЕЧАЕТ ЗА КНОПКУ "НАЗАД") ---
@admin_router.callback_query(
    F.data == "admin_main_menu",
    StateFilter(
        AdminStates.admin_menu,
        AdminStates.manage_services_menu,
        AdminStates.view_bookings_select_date,
        AdminStates.delete_booking_enter_id,
        AdminStates.add_service_name,
        AdminStates.add_service_price,
        AdminStates.add_service_duration,
        AdminStates.edit_service_select,
        AdminStates.edit_service_field,
        AdminStates.edit_service_enter_new_value,
        AdminStates.delete_service_select,
        AdminStates.delete_service_confirm,
        AdminStates.view_users,
        AdminStates.stats_menu,
        AdminStates.export_excel_menu,
        None
    )
)
async def admin_back_to_main_menu(callback_query: CallbackQuery, state: FSMContext):
    try:
        await callback_query.message.edit_text(
            "Добро пожаловать в админ-панель!",
            reply_markup=get_admin_main_menu_keyboard()
        )
    except TelegramBadRequest as e:
        logger.warning(f"TelegramBadRequest: {e} - не удалось изменить сообщение для возврата в админ-меню. Отправляем новое.")
        await callback_query.message.answer(
            "Добро пожаловать в админ-панель!",
            reply_markup=get_admin_main_menu_keyboard()
        )
    await state.set_state(AdminStates.admin_menu)
    await callback_query.answer()


# --- Главное меню админа (Просмотр броней) ---
@admin_router.callback_query(AdminStates.admin_menu, F.data == "admin_view_bookings")
async def admin_view_bookings_start(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "Выберите дату для просмотра броней:",
        reply_markup=get_admin_date_selection_keyboard()
    )
    await state.set_state(AdminStates.view_bookings_select_date)
    await callback_query.answer()

@admin_router.callback_query(AdminStates.view_bookings_select_date, F.data.startswith("admin_date_"))
async def admin_view_bookings_date_selected(callback_query: CallbackQuery, state: FSMContext):
    selected_date_str = callback_query.data.split("_")[2]
    bookings = get_all_bookings_for_date(selected_date_str)

    if not bookings:
        await callback_query.message.edit_text(
            f"На <b>{datetime.strptime(selected_date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b> броней нет.",
            reply_markup=get_admin_main_menu_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.admin_menu)
        await callback_query.answer()
        return

    bookings_text = f"<b>Бронирования на {datetime.strptime(selected_date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}:</b>\n\n"
    for booking in bookings:
        booking_id, tg_id, user_name, user_phone, service_name, service_duration, booking_date, booking_time, status, notified = booking

        display_status = {
            'active': 'Активна',
            'cancelled': 'Отменена',
        }.get(status, status)

        bookings_text += (
            f"ID: <code>{booking_id}</code>\n"
            f"👤: {user_name} (TG ID: <code>{tg_id if tg_id else 'N/A'}</code>)\n"
            f"📞: {user_phone if user_phone else 'Не указан'}\n"
            f"✨: {service_name} ({service_duration} мин)\n"
            f"⏰: {booking_time}\n"
            f"Статус: {display_status}\n"
            f"Напоминание: {'Отправлено' if notified else 'Не отправлено'}\n"
            f"---------------------------\n"
        )

    await callback_query.message.edit_text(
        bookings_text,
        reply_markup=get_admin_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.admin_menu)
    await callback_query.answer()

# Управление услугами
@admin_router.callback_query(F.data == "admin_manage_services")
async def admin_manage_services_menu(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "Выберите действие с услугами:",
        reply_markup=get_manage_services_keyboard()
    )
    await state.set_state(AdminStates.manage_services_menu)
    await callback_query.answer()

# Добавление услуги
@admin_router.callback_query(AdminStates.manage_services_menu, F.data == "admin_add_service")
async def admin_add_service_start(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите название новой услуги:", reply_markup=get_add_service_keyboard())
    await state.set_state(AdminStates.add_service_name)
    await callback_query.answer()

@admin_router.message(AdminStates.add_service_name)
async def admin_add_service_name_received(message: Message, state: FSMContext):
    service_name = message.text.strip()
    if not service_name:
        await message.answer("Название услуги не может быть пустым. Пожалуйста, введите название:", reply_markup=get_add_service_keyboard())
        return
    await state.update_data(new_service_name=service_name)
    await message.answer("Введите стоимость услуги (например, 1500):", reply_markup=get_add_service_keyboard())
    await state.set_state(AdminStates.add_service_price)

@admin_router.message(AdminStates.add_service_price)
async def admin_add_service_price_received(message: Message, state: FSMContext):
    try:
        service_price = float(message.text.strip())
        if service_price <= 0:
            await message.answer("Стоимость должна быть положительным числом. Пожалуйста, введите корректную стоимость:", reply_markup=get_add_service_keyboard())
            return
        await state.update_data(new_service_price=service_price)
        await message.answer("Введите длительность услуги в минутах (например, 60):", reply_markup=get_add_service_keyboard())
        await state.set_state(AdminStates.add_service_duration)
    except ValueError:
        await message.answer("Неверный формат стоимости. Пожалуйста, введите число:", reply_markup=get_add_service_keyboard())

@admin_router.message(AdminStates.add_service_duration)
async def admin_add_service_confirm(message: Message, state: FSMContext):
    try:
        duration_min = int(message.text.strip())
        if duration_min <= 0:
            await message.answer("Длительность должна быть положительным целым числом. Пожалуйста, введите корректную длительность:", reply_markup=get_add_service_keyboard())
            return
        
        user_data = await state.get_data()
        name = user_data.get("new_service_name")
        price = user_data.get("new_service_price")

        success, msg = add_service(name, price, duration_min)

        if success:
            await message.answer(f"✅ Услуга '{name}' (Стоимость: {price:.0f} тг, Длительность: {duration_min} мин) успешно добавлена!",
                                 reply_markup=get_manage_services_keyboard())
        else:
            await message.answer(f"❌ Ошибка при добавлении услуги: {msg}",
                                 reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
    except ValueError:
        await message.answer("Неверный формат длительности. Пожалуйста, введите целое число:", reply_markup=get_add_service_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при добавлении услуги: {e}")
        await message.answer("Произошла непредвиденная ошибка при добавлении услуги.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)

# Просмотр услуг
@admin_router.callback_query(AdminStates.manage_services_menu, F.data == "admin_view_services")
async def admin_view_services_list(callback_query: CallbackQuery, state: FSMContext):
    services = get_all_services()
    if not services:
        await callback_query.message.edit_text("Список услуг пуст.", reply_markup=get_manage_services_keyboard())
        await callback_query.answer()
        return

    services_text = "<b>Доступные услуги:</b>\n\n"
    for service_id, name, price, duration_min in services:
        services_text += f"ID: <code>{service_id}</code>\n"
        services_text += f"Название: {name}\n"
        services_text += f"Стоимость: {int(price)} ₸\n"
        services_text += f"Длительность: {duration_min} мин\n"
        services_text += "---------------------------\n"

    await callback_query.message.edit_text(
        services_text,
        reply_markup=get_manage_services_keyboard(),
        parse_mode="HTML"
    )
    await callback_query.answer()

# Редактирование услуги
@admin_router.callback_query(AdminStates.manage_services_menu, F.data == "admin_edit_service")
async def admin_edit_service_start(callback_query: CallbackQuery, state: FSMContext):
    services_keyboard = get_admin_service_selection_keyboard("edit_service_")
    if not services_keyboard:
        await callback_query.message.edit_text("Список услуг пуст. Сначала добавьте услугу.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
        await callback_query.answer()
        return

    await callback_query.message.edit_text(
        "Выберите услугу для редактирования:",
        reply_markup=services_keyboard
    )
    await state.set_state(AdminStates.edit_service_select)
    await callback_query.answer()

@admin_router.callback_query(AdminStates.edit_service_select, F.data.startswith("edit_service_"))
async def admin_edit_service_select_field(callback_query: CallbackQuery, state: FSMContext):
    logger.info(f"DEBUG: admin_edit_service_select_field triggered. Current state: {await state.get_state()}")
    logger.info(f"DEBUG: Callback Data received: '{callback_query.data}'")

    try:
        service_id_str = callback_query.data.split("_")[2]
        service_id = int(service_id_str)
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing service_id from callback_data '{callback_query.data}': {e}")
        await callback_query.answer("Произошла ошибка при выборе услуги. Пожалуйста, попробуйте еще раз.", show_alert=True)
        try:
            await callback_query.message.edit_text("Не удалось выбрать услугу из-за ошибки. Вернитесь в меню управления услугами.", reply_markup=get_manage_services_keyboard())
        except TelegramBadRequest:
            await callback_query.message.answer("Не удалось выбрать услугу из-за ошибки. Вернитесь в меню управления услугами.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
        return

    logger.info(f"DEBUG: Successfully extracted service_id: {service_id}")

    service = get_service(service_id)

    if not service:
        logger.warning(f"Service with ID {service_id} not found in DB during edit selection. Callback data: {callback_query.data}")
        await callback_query.answer("Услуга не найдена или была удалена. Пожалуйста, выберите другую услугу или вернитесь.", show_alert=True)
        try:
            await callback_query.message.edit_text("Услуга не найдена. Попробуйте выбрать другую или вернитесь в меню.", reply_markup=get_manage_services_keyboard())
        except TelegramBadRequest:
            await callback_query.message.answer("Услуга не найдена. Попробуйте выбрать другую или вернитесь в меню.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
        return

    await state.update_data(current_editing_service_id=service_id, current_editing_service_name=service[1])

    try:
        await callback_query.message.edit_text(
            f"Выбрана услуга: <b>{service[1]}</b> (ID: <code>{service_id}</code>).\nЧто вы хотите редактировать?",
            reply_markup=get_edit_service_field_keyboard(),
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        logger.warning(f"TelegramBadRequest when editing message in admin_edit_service_select_field: {e}. Attempting to send new message.")
        await callback_query.message.answer(
            f"Выбрана услуга: <b>{service[1]}</b> (ID: <code>{service_id}</code>).\nЧто вы хотите редактировать?",
            reply_markup=get_edit_service_field_keyboard(),
            parse_mode="HTML"
        )
    
    await state.set_state(AdminStates.edit_service_field)
    await callback_query.answer()

@admin_router.callback_query(AdminStates.edit_service_field, F.data.startswith("edit_service_field_"))
async def admin_edit_service_enter_new_value(callback_query: CallbackQuery, state: FSMContext):
    prefix = "edit_service_field_"
    if callback_query.data.startswith(prefix):
        field_to_edit = callback_query.data[len(prefix):]
    else:
        logger.error(f"Callback data did not start with expected prefix: {callback_query.data}")
        await callback_query.answer("Внутренняя ошибка при определении поля. Пожалуйста, попробуйте еще раз.", show_alert=True)
        await state.set_state(AdminStates.admin_menu)
        return

    logger.info(f"DEBUG: field_to_edit is: '{field_to_edit}' from callback_data: '{callback_query.data}'")
    user_data = await state.get_data()
    service_name = user_data.get("current_editing_service_name", "выбранной услуги")

    prompt = ""
    if field_to_edit == "name":
        prompt = "Введите новое название услуги:"
    elif field_to_edit == "price":
        prompt = "Введите новую стоимость услуги (например, 1500):"
    elif field_to_edit == "duration_min":
        prompt = "Введите новую длительность услуги в минутах (например, 60):"
    else:
        await callback_query.answer("Неизвестное поле для редактирования.", show_alert=True)
        await callback_query.message.edit_text(
            "Неизвестное поле для редактирования. Пожалуйста, выберите поле снова.",
            reply_markup=get_edit_service_field_keyboard()
        )
        await state.set_state(AdminStates.edit_service_field)
        return

    await state.update_data(current_editing_field=field_to_edit)
    message_text = f"Редактируем <b>{field_to_edit_display_name(field_to_edit)}</b> для <b>{service_name}</b>.\n{prompt}"
    reply_markup = None # Можно добавить кнопку "Назад" здесь, если нужно

    try:
        await callback_query.message.edit_text(message_text, parse_mode="HTML", reply_markup=reply_markup)
    except TelegramBadRequest as e:
        logger.warning(f"TelegramBadRequest: {e} - сообщение не изменено. Вероятно, повторный клик или избыточное изменение.")
        await callback_query.answer("Уже запрошено новое значение. Пожалуйста, введите его.")
        return

    await state.set_state(AdminStates.edit_service_enter_new_value)
    await callback_query.answer()

@admin_router.message(AdminStates.edit_service_enter_new_value)
async def admin_edit_service_save_value(message: Message, state: FSMContext):
    new_value_str = message.text.strip()
    user_data = await state.get_data()
    service_id = user_data.get("current_editing_service_id")
    field_name = user_data.get("current_editing_field")
    service_name_display = user_data.get("current_editing_service_name", "услуги")

    if not service_id or not field_name or not new_value_str:
        await message.answer("Ошибка: Не хватает данных для редактирования. Начните заново.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
        return

    error_msg = None

    if field_name == "name":
        if not new_value_str:
            error_msg = "Название услуги не может быть пустым."
    elif field_name == "price":
        try:
            float(new_value_str)
            if float(new_value_str) <= 0:
                error_msg = "Стоимость должна быть положительным числом."
        except ValueError:
            error_msg = "Неверный формат стоимости. Введите число."
    elif field_name == "duration_min":
        try:
            int(new_value_str)
            if int(new_value_str) <= 0:
                error_msg = "Длительность должна быть положительным целым числом."
        except ValueError:
            error_msg = "Неверный формат длительности. Введите целое число."

    if error_msg:
        await message.answer(f"❌ {error_msg} Попробуйте еще раз:", parse_mode="HTML")
        return

    success, msg = update_service(service_id, field_name, new_value_str)

    if success:
        await message.answer(f"✅ Услуга <b>{service_name_display}</b>: поле <b>{field_to_edit_display_name(field_name)}</b> успешно обновлено на <b>{new_value_str}</b>!",
                             parse_mode="HTML",
                             reply_markup=get_manage_services_keyboard())
    else:
        await message.answer(f"❌ Ошибка при обновлении услуги: {msg}", reply_markup=get_manage_services_keyboard())

    await state.set_state(AdminStates.manage_services_menu)

# Удаление услуги
@admin_router.callback_query(AdminStates.manage_services_menu, F.data == "admin_delete_service")
async def admin_delete_service_start(callback_query: CallbackQuery, state: FSMContext):
    services_keyboard = get_admin_service_selection_keyboard("delete_service_")
    if not services_keyboard:
        await callback_query.message.edit_text("Список услуг пуст. Нет ничего для удаления.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
        await callback_query.answer()
        return

    await callback_query.message.edit_text(
        "Выберите услугу для удаления:",
        reply_markup=services_keyboard
    )
    await state.set_state(AdminStates.delete_service_select)
    await callback_query.answer()

@admin_router.callback_query(AdminStates.delete_service_select, F.data.startswith("delete_service_"))
async def admin_delete_service_confirm(callback_query: CallbackQuery, state: FSMContext):
    service_id = int(callback_query.data.split("_")[2])
    service = get_service(service_id)
    if not service:
        await callback_query.message.edit_text("Услуга не найдена. Попробуйте снова.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
        await callback_query.answer()
        return

    await state.update_data(service_to_delete_id=service_id, service_to_delete_name=service[1])
    await callback_query.message.edit_text(
        f"Вы действительно хотите удалить услугу <b>{service[1]}</b> (ID: <code>{service_id}</code>) и все связанные с ней бронирования?",
        reply_markup=get_confirm_delete_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.delete_service_confirm)
    await callback_query.answer()

# Удаление услуги по ID (если пользователь вводит ID вместо нажатия кнопки)
@admin_router.message(AdminStates.delete_service_select)
async def admin_delete_service_by_id(message: Message, state: FSMContext):
    try:
        service_id = int(message.text.strip())
        service = get_service(service_id)
        if not service:
            await message.answer("Услуга с таким ID не найдена. Попробуйте ввести ID снова или выберите из списка.",
                                 reply_markup=get_admin_service_selection_keyboard("delete_service_"))
            return

        await state.update_data(service_to_delete_id=service_id, service_to_delete_name=service[1])
        await message.answer(
            f"Вы действительно хотите удалить услугу <b>{service[1]}</b> (ID: <code>{service_id}</code>) и все связанные с ней бронирования?",
            reply_markup=get_confirm_delete_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(AdminStates.delete_service_confirm)
    except ValueError:
        await message.answer("Неверный формат ID. Введите число. Попробуйте снова или выберите из списка.",
                             reply_markup=get_admin_service_selection_keyboard("delete_service_"))


@admin_router.callback_query(AdminStates.delete_service_confirm, F.data == "confirm_delete")
async def admin_delete_service_execute(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    service_id = user_data.get("service_to_delete_id")
    service_name = user_data.get("service_to_delete_name")

    if not service_id:
        await callback_query.message.edit_text("Ошибка: Невозможно удалить услугу. Попробуйте сначала выбрать ее.", reply_markup=get_manage_services_keyboard())
        await state.set_state(AdminStates.manage_services_menu)
        await callback_query.answer()
        return

    success, msg = delete_service(service_id)
    if success:
        await callback_query.message.edit_text(f"✅ Услуга <b>{service_name}</b> и связанные бронирования успешно удалены.",
                                               parse_mode="HTML",
                                               reply_markup=get_manage_services_keyboard())
    else:
        await callback_query.message.edit_text(f"❌ Ошибка при удалении услуги: {msg}",
                                               reply_markup=get_manage_services_keyboard())

    await state.set_state(AdminStates.manage_services_menu)
    await callback_query.answer()

@admin_router.callback_query(AdminStates.delete_service_confirm, F.data == "cancel_delete")
async def admin_delete_service_cancel(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Удаление услуги отменено.", reply_markup=get_manage_services_keyboard())
    await state.set_state(AdminStates.manage_services_menu)
    await callback_query.answer()

# Удалить бронь
@admin_router.callback_query(AdminStates.admin_menu, F.data == "admin_delete_booking")
async def admin_delete_booking_enter_id(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text("Введите ID бронирования, которое хотите удалить:")
    await state.set_state(AdminStates.delete_booking_enter_id)
    await callback_query.answer()

@admin_router.message(AdminStates.delete_booking_enter_id)
async def admin_delete_booking_execute(message: Message, state: FSMContext):
    try:
        booking_id = int(message.text.strip())
        success = cancel_booking(booking_id)
        if success:
            await message.answer(f"✅ Бронь ID: <code>{booking_id}</code> успешно удалена!",
                                 parse_mode="HTML",
                                 reply_markup=get_admin_main_menu_keyboard())
        else:
            await message.answer(f"❌ Ошибка при удалении брони ID: <code>{booking_id}</code>. Возможно, она не найдена или уже не активна.",
                                 parse_mode="HTML",
                                 reply_markup=get_admin_main_menu_keyboard())
        await state.set_state(AdminStates.admin_menu)
    except ValueError:
        await message.answer("Неверный формат ID бронирования. Введите число.")
    except Exception as e:
        logger.error(f"Ошибка при удалении брони: {e}")
        await message.answer("Произошла непредвиденная ошибка при удалении брони.", reply_markup=get_admin_main_menu_keyboard())
        await state.set_state(AdminStates.admin_menu)

# Просмотр списка пользователей
@admin_router.callback_query(AdminStates.admin_menu, F.data == "admin_view_users")
async def admin_view_users_list(callback_query: CallbackQuery, state: FSMContext):
    users = get_all_users()

    if not users:
        await callback_query.message.edit_text(
            "Список пользователей пуст.",
            reply_markup=get_admin_main_menu_keyboard()
        )
        await state.set_state(AdminStates.admin_menu)
        await callback_query.answer()
        return

    users_text = "<b>Зарегистрированные пользователи:</b>\n\n"
    # Обновлено: в users_text добавлено отображение registration_date, так как оно было в DB.
    # Если get_all_users() не возвращает registration_date, эту строку нужно будет убрать.
    for user_id, telegram_id, name, phone_number in users: 
        users_text += (
            f"ID: <code>{user_id}</code>\n"
            f"👤: {name}\n"
            f"📞: {phone_number if phone_number else 'Не указан'}\n"
            f"TG ID: <code>{telegram_id if telegram_id else 'N/A'}</code>\n"
            f"---------------------------\n"
        )

    await callback_query.message.edit_text(
        users_text,
        reply_markup=get_admin_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.admin_menu)
    await callback_query.answer()

# Статистика
@admin_router.callback_query(AdminStates.admin_menu, F.data == "admin_stats")
async def admin_show_stats(callback_query: CallbackQuery, state: FSMContext):
    total_bookings_raw = get_all_bookings_in_system()
    total_bookings = len(total_bookings_raw)
    active_bookings = len([b for b in total_bookings_raw if b[8] == 'active'])

    stats_text = (
        "📊 <b>Статистика:</b>\n\n"
        f"Всего бронирований: {total_bookings}\n"
        f"Активных бронирований: {active_bookings}\n"
        "\n<i>Более подробная статистика в разработке...</i>"
    )
    await callback_query.message.edit_text(
        stats_text,
        reply_markup=get_admin_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.admin_menu)
    await callback_query.answer()

# Экспорт в Excel
@admin_router.callback_query(AdminStates.admin_menu, F.data == "admin_export_excel")
async def admin_export_excel(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "Функция экспорта в Excel пока в разработке.",
        reply_markup=get_admin_main_menu_keyboard()
    )
    await state.set_state(AdminStates.admin_menu)
    await callback_query.answer()

# Выход из админ-панели
@admin_router.callback_query(AdminStates.admin_menu, F.data == "admin_exit")
async def admin_exit_panel(callback_query: CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    await callback_query.message.answer( # <-- Используем message.answer для нового сообщения
        "Вы вышли из админ-панели.",
        reply_markup=get_main_menu_keyboard(user_id) # <-- Возвращаем пользовательскую Reply-клавиатуру
    )
    # Удаляем Inline-клавиатуру админки из предыдущего сообщения
    try:
        await callback_query.message.delete() 
    except TelegramBadRequest as e:
        logger.warning(f"Не удалось удалить сообщение с админской клавиатурой: {e}")
    
    await state.clear()
    await callback_query.answer()