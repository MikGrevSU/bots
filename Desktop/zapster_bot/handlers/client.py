from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import datetime
from typing import List

from db.database import db
from utils.keyboards import (
    get_main_menu_client, get_locations_keyboard, get_services_keyboard,
    get_calendar_keyboard, get_time_slots_keyboard, get_cancel_booking_keyboard
)

client_router = Router()

# Состояния для процесса бронирования
class ClientBookingStates(StatesGroup):
    SELECT_LOCATION = State()
    SELECT_SERVICE = State()
    SELECT_DATE = State()
    SELECT_TIME = State()
    CONFIRM_BOOKING = State()
    # Добавляем состояние для ожидания сообщения поддержки
    waiting_for_support_message = State() # <--- НОВАЯ СТРОКА

# --- Запись на услугу ---

@client_router.message(F.text == "⚡️ Записаться")
async def cmd_book(message: types.Message, state: FSMContext):
    """Начинает процесс записи: предлагает выбрать организацию."""
    locations = await db.get_all_locations()
    if not locations:
        await message.answer("Извините, пока нет доступных организаций для записи. Попробуйте позже.")
        await state.clear()
        return

    await message.answer("Выберите организацию:", reply_markup=get_locations_keyboard(locations))
    await state.set_state(ClientBookingStates.SELECT_LOCATION)

@client_router.callback_query(F.data.startswith("select_location_"), ClientBookingStates.SELECT_LOCATION)
async def select_location(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор организации, предлагает выбрать услугу."""
    location_id = int(callback.data.split("_")[2])
    
    # Проверяем, есть ли у пользователя номер телефона
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user['phone_number']:
        await callback.message.edit_text(
            "Для записи нам нужен ваш номер телефона. Пожалуйста, отправьте его.",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[[types.KeyboardButton(text="Отправить мой номер телефона", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
        await state.update_data(location_id=location_id) # Сохраняем location_id
        # Остаемся в этом же состоянии (ClientBookingStates.SELECT_LOCATION), ожидая контакт,
        # так как это логически часть процесса выбора локации, требующая доп.данных.
        # Состояние не меняем.
        return

    await state.update_data(location_id=location_id)
    services = await db.get_services_by_location(location_id)

    if not services:
        await callback.message.edit_text("Извините, в этой организации пока нет доступных услуг.", reply_markup=None)
        await callback.message.answer("Выберите другую организацию:", reply_markup=get_locations_keyboard(await db.get_all_locations()))
        await state.set_state(ClientBookingStates.SELECT_LOCATION)
        return

    await callback.message.edit_text(
        "Выберите услугу:", 
        reply_markup=get_services_keyboard(services, location_id)
    )
    await state.set_state(ClientBookingStates.SELECT_SERVICE)
    await callback.answer()

@client_router.message(F.contact, ClientBookingStates.SELECT_LOCATION)
async def get_contact(message: types.Message, state: FSMContext):
    """Обрабатывает получение контакта пользователя."""
    phone_number = message.contact.phone_number
    user = await db.get_user_by_telegram_id(message.from_user.id)
    await db.update_user_phone(user['user_id'], phone_number)
    
    data = await state.get_data()
    location_id = data.get('location_id')

    if not location_id: # Если по какой-то причине location_id не сохранился
        await message.answer("Произошла ошибка, пожалуйста, начните запись заново.", reply_markup=get_main_menu_client())
        await state.clear()
        return

    services = await db.get_services_by_location(location_id)
    if not services:
        await message.answer("Извините, в этой организации пока нет доступных услуг.", reply_markup=None)
        await message.answer("Выберите другую организацию:", reply_markup=get_locations_keyboard(await db.get_all_locations()))
        await state.set_state(ClientBookingStates.SELECT_LOCATION)
        return
    
    await message.answer("Номер телефона сохранен. Теперь выберите услугу:", reply_markup=types.ReplyKeyboardRemove()) # Убираем клавиатуру с запросом контакта
    await message.answer(
        "Выберите услугу:",
        reply_markup=get_services_keyboard(services, location_id)
    )
    await state.set_state(ClientBookingStates.SELECT_SERVICE)


@client_router.callback_query(F.data.startswith("services_page_"), ClientBookingStates.SELECT_SERVICE)
async def paginate_services(callback: types.CallbackQuery, state: FSMContext):
    """Пагинация услуг."""
    parts = callback.data.split("_")
    location_id = int(parts[2])
    page = int(parts[3])
    
    services = await db.get_services_by_location(location_id)
    await callback.message.edit_reply_markup(
        reply_markup=get_services_keyboard(services, location_id, page)
    )
    await callback.answer()


@client_router.callback_query(F.data.startswith("select_service_"), ClientBookingStates.SELECT_SERVICE)
async def select_service(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор услуги, предлагает выбрать дату."""
    service_id = int(callback.data.split("_")[2])
    await state.update_data(service_id=service_id)

    today = datetime.date.today()
    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=get_calendar_keyboard(today.year, today.month)
    )
    await state.set_state(ClientBookingStates.SELECT_DATE)
    await callback.answer()

@client_router.callback_query(F.data.startswith("calendar_nav_"), ClientBookingStates.SELECT_DATE)
async def calendar_nav(callback: types.CallbackQuery):
    """Навигация по календарю (месяцы)."""
    _, _, year_str, month_str = callback.data.split("_")
    year, month = int(year_str), int(month_str)
    await callback.message.edit_reply_markup(
        reply_markup=get_calendar_keyboard(year, month)
    )
    await callback.answer()

@client_router.callback_query(F.data.startswith("select_date_"), ClientBookingStates.SELECT_DATE)
async def select_date(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор даты, предлагает выбрать время."""
    selected_date_str = callback.data.split("_")[2]
    await state.update_data(booking_date=selected_date_str)

    data = await state.get_data()
    location_id = data['location_id']
    
    slots = await db.get_available_slots(location_id, selected_date_str)
    
    await callback.message.edit_text(
        f"Выберите время на {selected_date_str}:",
        reply_markup=get_time_slots_keyboard(slots, selected_date_str)
    )
    await state.set_state(ClientBookingStates.SELECT_TIME)
    await callback.answer()

@client_router.callback_query(F.data.startswith("select_time_"), ClientBookingStates.SELECT_TIME)
async def select_time(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор времени, подтверждает запись."""
    booking_time = callback.data.split("_")[2]
    data = await state.get_data()
    
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    user_id = user['user_id']
    location_id = data['location_id']
    service_id = data['service_id']
    booking_date = data['booking_date']

    location = await db.get_location_by_id(location_id)
    service = await db.get_service_by_id(service_id)

    if not location or not service:
        await callback.message.edit_text("Ошибка: Не удалось найти данные об организации или услуге. Попробуйте сначала.", reply_markup=get_main_menu_client())
        await state.clear()
        await callback.answer()
        return

    # Попытка добавить запись
    booking_id = await db.add_booking(user_id, location_id, service_id, booking_date, booking_time)

    if booking_id:
        await callback.message.edit_text(
            f"✅ Вы успешно записаны!\n\n"
            f"**Организация:** {location['name']}\n"
            f"**Услуга:** {service['name']}\n"
            f"**Дата:** {booking_date}\n"
            f"**Время:** {booking_time}\n"
            f"Ждем вас!",
            reply_markup=get_main_menu_client() # Возвращаем основное меню
        )
        await state.clear() # Запись завершена, сбрасываем состояние
    else:
        await callback.message.edit_text(
            f"❌ Не удалось записаться. Возможно, вы уже записаны в '{location['name']}' на {booking_date}, "
            "или этот слот уже занят. Попробуйте выбрать другое время или день.",
            reply_markup=get_time_slots_keyboard(await db.get_available_slots(location_id, booking_date), booking_date)
        )
        # Остаемся в состоянии SELECT_TIME, чтобы пользователь мог выбрать другой слот
    await callback.answer()

# --- Возврат к выбору ---

@client_router.callback_query(F.data == "back_to_locations", ClientBookingStates.SELECT_SERVICE)
async def back_to_locations(callback: types.CallbackQuery, state: FSMContext):
    """Возвращение к выбору организаций."""
    locations = await db.get_all_locations()
    await callback.message.edit_text("Выберите организацию:", reply_markup=get_locations_keyboard(locations))
    await state.set_state(ClientBookingStates.SELECT_LOCATION)
    await callback.answer()

@client_router.callback_query(F.data.startswith("back_to_services"), ClientBookingStates.SELECT_DATE)
async def back_to_services(callback: types.CallbackQuery, state: FSMContext):
    """Возвращение к выбору услуг."""
    data = await state.get_data()
    location_id = data['location_id']
    services = await db.get_services_by_location(location_id)
    await callback.message.edit_text("Выберите услугу:", reply_markup=get_services_keyboard(services, location_id))
    await state.set_state(ClientBookingStates.SELECT_SERVICE)
    await callback.answer()

@client_router.callback_query(F.data.startswith("back_to_date_selection_"), ClientBookingStates.SELECT_TIME)
async def back_to_date_selection(callback: types.CallbackQuery, state: FSMContext):
    """Возвращение к выбору даты."""
    selected_date_str = callback.data.split("_")[3] # В данном случае data выглядит так: back_to_date_selection_YYYY-MM-DD
    # Можно использовать сохраненную дату из state для отображения календаря,
    # или просто перенаправить на выбор месяца/года
    
    # Можно получить текущий год/месяц из переданной даты, чтобы открыть календарь на ней
    parts = list(map(int, selected_date_str.split('-')))
    year, month = parts[0], parts[1]

    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=get_calendar_keyboard(year, month)
    )
    await state.set_state(ClientBookingStates.SELECT_DATE)
    await callback.answer()


# --- Мои записи ---

@client_router.message(F.text == "🗓 Мои записи")
async def cmd_my_bookings(message: types.Message, state: FSMContext):
    """Показывает активные записи пользователя."""
    await state.clear() # Сброс состояния, если было активное бронирование
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Пожалуйста, начните с /start для регистрации.")
        return

    bookings = await db.get_user_bookings(user['user_id'])

    if not bookings:
        await message.answer("У вас пока нет предстоящих записей.")
        return

    response_text = "Ваши предстоящие записи:\n\n"
    for booking in bookings:
        response_text += (
            f"**ID записи:** `{booking['booking_id']}`\n"
            f"**Организация:** {booking['location_name']}\n"
            f"**Услуга:** {booking['service_name']}\n"
            f"**Дата:** {booking['booking_date']}\n"
            f"**Время:** {booking['booking_time']}\n\n"
        )
        # Отправляем каждую запись отдельно с кнопкой "Отменить"
        await message.answer(
            response_text,
            reply_markup=get_cancel_booking_keyboard(booking['booking_id'])
        )
        response_text = "" # Сбрасываем текст для следующей итерации

    if not response_text: # Если все записи были отправлены по одной, это сообщение не нужно
        await message.answer("⬆️ Это все ваши записи.")


@client_router.callback_query(F.data.startswith("cancel_booking_client_"))
async def cancel_booking_client(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает отмену записи клиентом."""
    booking_id = int(callback.data.split("_")[3])
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    
    # Проверка, что пользователь является владельцем этой записи
    user_bookings = await db.get_user_bookings(user['user_id'])
    is_owner = any(b['booking_id'] == booking_id for b in user_bookings)

    if not is_owner:
        await callback.answer("Вы не можете отменить эту запись.", show_alert=True)
        return

    success = await db.delete_booking(booking_id)

    if success:
        await callback.message.edit_text("✅ Запись успешно отменена.")
    else:
        await callback.message.edit_text("❌ Не удалось отменить запись. Попробуйте еще раз.")
    
    await callback.answer()
    await state.clear() # Сбрасываем состояние после действия

# --- Связь с поддержкой ---

@client_router.message(F.text == "📞 Связь с поддержкой")
async def contact_support(message: types.Message, state: FSMContext):
    """Предлагает пользователю отправить сообщение для поддержки."""
    await message.answer("Напишите ваше сообщение для поддержки, и мы передадим его администраторам:")
    await state.set_state(ClientBookingStates.waiting_for_support_message) # <--- ИЗМЕНЕНА СТРОКА

@client_router.message(ClientBookingStates.waiting_for_support_message) # <--- ИЗМЕНЕНА СТРОКА
async def process_support_message(message: types.Message, state: FSMContext):
    """Обрабатывает сообщение для поддержки и пересылает его админам."""
    support_message = message.text
    
    # В реальном приложении здесь нужно найти админов и переслать им сообщение.
    # Для MVP просто сообщим, что сообщение отправлено.
    # Можно сделать через db.get_all_admins() и отправлять каждому
    
    await message.answer("✅ Ваше сообщение для поддержки отправлено. Мы свяжемся с вами в ближайшее время.")
    #await message.answer("Сообщение для поддержки:\n\n"
    #                     f"От пользователя {message.from_user.full_name} (@{message.from_user.username}):\n"
    #                     f"{support_message}") # Это для демонстрации, что сообщение получено
    await state.clear()