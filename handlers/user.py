# project/handlers/user.py
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from db import (
    add_user, get_user, update_user, get_all_services, get_service,
    get_free_slots, create_booking, get_user_active_booking,
    cancel_booking, get_user_booking_history,
    get_user_active_booking_full_details
)
from keyboards.user import (
    get_phone_request_keyboard, get_main_menu_keyboard, get_cancel_keyboard,
    get_services_keyboard, get_dates_keyboard, get_time_slots_keyboard,
    get_booking_action_keyboard, get_confirm_cancel_keyboard,
    get_confirmation_keyboard
)
from states import UserRegistration, UserBooking
from datetime import datetime, timedelta

user_router = Router()
logger = logging.getLogger(__name__)

@user_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    
    # ... (код для регистрации пользователя, если он есть)
    
    await message.answer(
        f"Привет, {user_name}! Добро пожаловать в наш салон! 👋",
        reply_markup=get_main_menu_keyboard(user_id) # <-- ИЗМЕНИТЕ ЭТУ СТРОКУ
    )
    await state.clear()


@user_router.message(UserRegistration.waiting_for_name, F.text)
async def process_name(message: Message, state: FSMContext):
    user_name = message.text.strip()
    if user_name.lower() == "отмена":
        await state.clear()
        await message.answer("Регистрация отменена. Вы можете начать заново, набрав /start.",
                             reply_markup=get_main_menu_keyboard())
        return

    if not user_name:
        await message.answer("Пожалуйста, введите ваше имя.")
        return

    await state.update_data(name=user_name)
    await message.answer(
        f"Отлично, {user_name}! Теперь, пожалуйста, поделись своим номером телефона, "
        "чтобы мы могли связаться с тобой для подтверждения записи.",
        reply_markup=get_phone_request_keyboard()
    )
    await state.set_state(UserRegistration.waiting_for_phone)

@user_router.message(UserRegistration.waiting_for_phone, F.contact)
async def process_phone(message: Message, state: FSMContext):
    user_tg_id = message.from_user.id
    phone_number = message.contact.phone_number
    user_data = await state.get_data()
    user_name = user_data.get("name")

    if not user_name:
        user_name = message.from_user.full_name

    add_user(user_tg_id, user_name, phone_number)

    await message.answer(
        "Спасибо! Регистрация завершена. Теперь вы можете пользоваться всеми функциями бота.",
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()

@user_router.message(UserRegistration.waiting_for_phone, F.text)
async def process_phone_text_input(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await state.clear()
        await message.answer("Регистрация отменена. Вы можете начать заново, набрав /start.",
                             reply_markup=get_main_menu_keyboard())
        return

    await message.answer(
        "Пожалуйста, используйте кнопку '📱 Отправить номер' для удобства, "
        "или введите номер телефона в международном формате (например, +79XXXXXXXXX)."
    )

@user_router.message(F.text == "✍️ Записаться на услугу")
async def start_booking_service(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Пожалуйста, начните с команды /start.")
        return

    active_booking = get_user_active_booking(user[0])
    if active_booking:
        await message.answer(
            f"У вас уже есть активная запись:\n"
            f"<b>{active_booking[1]}</b> ({active_booking[2]} мин.) на <b>{active_booking[3]}</b> в <b>{active_booking[4]}</b>.\n"
            "Вы можете отменить её, чтобы сделать новую.",
            reply_markup=get_booking_action_keyboard(active_booking[0]),
            parse_mode="HTML"
        )
        return

    services = get_all_services()
    if not services:
        await message.answer("Извините, сейчас нет доступных услуг. Попробуйте позже.")
        return

    await message.answer("Выберите услугу:", reply_markup=get_services_keyboard(services))
    await state.set_state(UserBooking.waiting_for_service)

@user_router.callback_query(UserBooking.waiting_for_service, F.data.startswith("service_"))
async def select_service_for_booking(callback_query: CallbackQuery, state: FSMContext):
    service_id = int(callback_query.data.split("_")[1])
    service = get_service(service_id=service_id)

    if not service:
        await callback_query.message.answer("Выбранная услуга не найдена. Попробуйте снова.")
        await state.clear()
        return

    service_name = service[1]
    service_price = service[2]
    service_duration = service[3] # Получаем duration

    if service_price is None:
        await callback_query.message.answer("У выбранной услуги не указана стоимость. Пожалуйста, сообщите администратору или выберите другую услугу.")
        await state.clear()
        return

    await state.update_data(
        selected_service_id=service_id,        # <-- Сохраняем ID
        selected_service_name=service_name,
        selected_service_duration=service_duration, # <-- Сохраняем duration
        selected_service_price=service_price
    )
    
    await callback_query.message.edit_text(
        f"Вы выбрали: <b>{service_name}</b> (Цена: {int(service_price)} ₸).\nТеперь выберите дату:",
        reply_markup=get_dates_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(UserBooking.waiting_for_date)
    await callback_query.answer()

# Новый обработчик для кнопки "Назад к выбору даты"
@user_router.callback_query(F.data == "back_to_date_selection", UserBooking.waiting_for_time)
async def back_to_date_selection(callback_query: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    selected_service_name = user_data.get("selected_service_name")

    await callback_query.message.edit_text(
        f"Вы выбрали: <b>{selected_service_name}</b>.\nВыберите дату:",
        reply_markup=get_dates_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(UserBooking.waiting_for_date)
    await callback_query.answer()

@user_router.callback_query(F.data == "back_to_service_selection", UserBooking.waiting_for_date)
async def back_to_service_selection(callback_query: CallbackQuery, state: FSMContext):
    services = get_all_services()
    if not services:
        await callback_query.message.edit_text("Извините, сейчас нет доступных услуг. Попробуйте позже.")
        await state.clear()
        await callback_query.message.answer("Что еще могу для вас сделать?", reply_markup=get_main_menu_keyboard())
        return

    await callback_query.message.edit_text("Выберите услугу:", reply_markup=get_services_keyboard(services))
    await state.set_state(UserBooking.waiting_for_service)
    await callback_query.answer()

# Обработчик для "Нет свободных слотов на эту дату"
@user_router.callback_query(F.data == "no_slots", UserBooking.waiting_for_time)
async def handle_no_slots(callback_query: CallbackQuery):
    await callback_query.answer("Пожалуйста, выберите другую дату.", show_alert=True)


@user_router.callback_query(UserBooking.waiting_for_date, F.data.startswith("date_"))
async def select_date_for_booking(callback_query: CallbackQuery, state: FSMContext):
    selected_date_str = callback_query.data.split("_")[1]
    user_data = await state.get_data()
    selected_service_name = user_data.get("selected_service_name")
    selected_service_duration = user_data.get("selected_service_duration")
    selected_service_price = user_data.get("selected_service_price")

    # Усиленная проверка данных здесь тоже
    if not (selected_service_name and selected_service_duration and selected_service_price is not None):
        await callback_query.message.answer("Произошла ошибка (неполные данные об услуге). Пожалуйста, начните запись заново.")
        await state.clear()
        return

    try:
        selected_date_obj = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        if selected_date_obj < datetime.now().date():
            await callback_query.answer("Нельзя выбрать прошедшую дату. Пожалуйста, выберите корректную дату.", show_alert=True)
            return
    except ValueError:
        await callback_query.answer("Неверный формат даты. Пожалуйста, попробуйте снова.", show_alert=True)
        return

    # Запрашиваем свободные слоты без slot_step_min
    time_slots = get_free_slots(selected_date_str, selected_service_duration) 

    await state.update_data(selected_booking_date=selected_date_str) # <-- Сохраняем дату
    await callback_query.message.edit_text(
        f"Вы выбрали: <b>{selected_service_name}</b> (Цена: {int(selected_service_price)} ₸).\n"
        f"Дата: <b>{datetime.strptime(selected_date_str, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>.\n"
        "Выберите удобное время:",
        reply_markup=get_time_slots_keyboard(time_slots),
        parse_mode="HTML"
    )
    await state.set_state(UserBooking.waiting_for_time)
    await callback_query.answer()

@user_router.callback_query(UserBooking.waiting_for_time, F.data.startswith("time_"))
async def select_time_for_booking(callback_query: CallbackQuery, state: FSMContext):
    selected_time_str = callback_query.data.split("_")[1]
    user_data = await state.get_data()
    user_tg_id = callback_query.from_user.id
    
    user_db_info = get_user(user_tg_id)

    if not user_db_info:
        await callback_query.message.answer(
            "Пожалуйста, зарегистрируйтесь, набрав /start, прежде чем записываться на услугу."
        )
        await state.clear()
        await callback_query.answer()
        return

    user_name = user_db_info[2]

    # Получаем все необходимые данные
    selected_service_id = user_data.get("selected_service_id") # <-- Убедитесь, что этот ID есть
    selected_service_name = user_data.get("selected_service_name")
    selected_service_duration = user_data.get("selected_service_duration") # <-- Убедитесь, что duration есть
    selected_service_price = user_data.get("selected_service_price")
    selected_booking_date = user_data.get("selected_booking_date")
    
    # Расширенная проверка на наличие всех критически важных данных
    if not (selected_service_id and selected_service_name and selected_service_duration and selected_booking_date and user_name and selected_time_str):
        await callback_query.message.answer(
            "Произошла ошибка (не хватает данных для записи). Пожалуйста, начните запись заново через '✍️ Записаться на услугу'."
        )
        await state.clear()
        await callback_query.answer()
        return

    # Особая проверка для цены, так как она вызвала ошибку
    if selected_service_price is None:
        if selected_service_id:
            service_from_db = get_service(selected_service_id)
            if service_from_db and service_from_db[2] is not None:
                selected_service_price = service_from_db[2]
                await state.update_data(selected_service_price=selected_service_price) # <-- СОХРАНЯЕМ ОБРАТНО!
            else:
                await callback_query.message.answer(
                    "К сожалению, не удалось получить стоимость выбранной услуги. Пожалуйста, попробуйте другую услугу или свяжитесь с администратором."
                )
                await state.clear()
                await callback_query.answer()
                return
        else:
            await callback_query.message.answer(
                "Произошла ошибка (данные об услуге потеряны). Пожалуйста, начните запись заново."
            )
            await state.clear()
            await callback_query.answer()
            return


    # Сохраняем выбранное время в FSM контекст
    await state.update_data(selected_booking_time=selected_time_str)

    # Формируем сводку для подтверждения
    confirmation_text = (
        f"<b>Пожалуйста, проверьте детали вашей записи:</b>\n\n"
        f"🙋‍♂️ Имя: <b>{user_name}</b>\n"
        f"✨ Услуга: <b>{selected_service_name}</b>\n"
        f"💰 Стоимость: <b>{int(selected_service_price)} ₸</b>\n"
        f"🗓 Дата: <b>{datetime.strptime(selected_booking_date, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
        f"⏰ Время: <b>{selected_time_str}</b>\n\n"
        f"Все верно?"
    )

    await callback_query.message.edit_text(
        confirmation_text,
        reply_markup=get_confirmation_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(UserBooking.waiting_for_confirmation)
    await callback_query.answer()



@user_router.callback_query(UserBooking.waiting_for_confirmation, F.data == "confirm_booking")
async def process_confirm_booking(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    user_data = await state.get_data()
    user_tg_id = callback_query.from_user.id
    user_db_info = get_user(user_tg_id)

    # Проверяем, что пользователь зарегистрирован и есть его данные
    if not user_db_info:
        await callback_query.message.answer(
            "Ваши данные не найдены. Пожалуйста, начните процесс заново, набрав /start."
        )
        await state.clear()
        await callback_query.answer()
        return

    user_id_in_db = user_db_info[0]
    user_name = user_db_info[2]
    user_phone = user_db_info[3] # Может быть None, если номер не был предоставлен

    selected_service_id = user_data.get("selected_service_id")
    selected_service_name = user_data.get("selected_service_name")
    selected_service_duration = user_data.get("selected_service_duration")
    selected_service_price = user_data.get("selected_service_price") # Здесь тоже может быть None

    selected_booking_date = user_data.get("selected_booking_date")
    selected_booking_time = user_data.get("selected_booking_time")

    # Дополнительная проверка всех данных перед созданием брони
    if not all([selected_service_id, selected_service_name, selected_service_duration, 
                selected_service_price is not None, selected_booking_date, selected_booking_time]):
        await callback_query.message.answer(
            "Произошла ошибка (не хватает данных для подтверждения). Пожалуйста, начните запись заново."
        )
        await state.clear()
        await callback_query.answer()
        return

    success, message_text = create_booking(
        user_id_in_db, selected_service_id, selected_booking_date, selected_booking_time
    )

    if success:
        await callback_query.message.edit_text(
            f"✅ Запись на <b>{selected_service_name}</b> "
            f"на <b>{datetime.strptime(selected_booking_date, '%Y-%m-%d').strftime('%d.%m.%Y')}</b> "
            f"в <b>{selected_booking_time}</b> успешно создана!\n"
            "Ждем вас!",
            parse_mode="HTML",
            reply_markup=None # Убираем инлайн-клавиатуру
        )
        await callback_query.message.answer("Что еще могу для вас сделать?", reply_markup=get_main_menu_keyboard())

        # Уведомление администраторам о новой записи
        admin_notification_text = (
            f"🎉 **НОВАЯ ЗАПИСЬ!** 🎉\n\n"
            f"**Пользователь:** {user_name} (TG ID: `{user_tg_id}`)\n"
            f"**Телефон:** `{user_phone if user_phone else 'Не указан'}`\n" # Обработка None для телефона
            f"**Услуга:** `{selected_service_name}` ({selected_service_duration} мин, {int(selected_service_price)} ₸)\n"
            f"**Дата:** `{datetime.strptime(selected_booking_date, '%Y-%m-%d').strftime('%d.%m.%Y')}`\n"
            f"**Время:** `{selected_booking_time}`"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_notification_text, parse_mode="Markdown")
            except Exception as e:
                print(f"Не удалось отправить уведомление админу {admin_id}: {e}")

    else:
        await callback_query.message.edit_text(
            f"🚫 Не удалось создать запись: {message_text}\n"
            "Пожалуйста, попробуйте снова или выберите другое время.",
            parse_mode="HTML",
            reply_markup=None # Убираем инлайн-клавиатуру
        )
        await callback_query.message.answer("Что еще могу для вас сделать?", reply_markup=get_main_menu_keyboard())

    await state.clear()
    await callback_query.answer()

@user_router.callback_query(UserBooking.waiting_for_confirmation, F.data == "cancel_booking_process")
async def process_cancel_booking_from_confirmation(callback_query: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.edit_text("Запись отменена. Вы можете выбрать другую услугу или дату.", reply_markup=None)
    await callback_query.message.answer("Что еще могу для вас сделать?", reply_markup=get_main_menu_keyboard())
    await callback_query.answer()

@user_router.message(F.text == "🗓️ Мои записи")
async def show_my_bookings(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Пожалуйста, начните с команды /start.")
        return

    active_booking = get_user_active_booking(user[0])
    if active_booking:
        booking_id, service_name, duration_min, booking_date, booking_time = active_booking
        await message.answer(
            f"<b>Ваша активная запись:</b>\n"
            f"Услуга: <b>{service_name}</b> ({duration_min} мин.)\n"
            f"Дата: <b>{datetime.strptime(booking_date, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
            f"Время: <b>{booking_time}</b>",
            reply_markup=get_booking_action_keyboard(booking_id),
            parse_mode="HTML"
        )
    else:
        await message.answer("У вас нет активных записей.")

@user_router.callback_query(F.data.startswith("cancel_booking_"))
async def request_cancel_booking(callback_query: CallbackQuery):
    booking_id = int(callback_query.data.split("_")[2])
    await callback_query.message.edit_text(
        "Вы уверены, что хотите отменить эту запись?",
        reply_markup=get_confirm_cancel_keyboard(booking_id)
    )
    await callback_query.answer()

@user_router.callback_query(F.data.startswith("confirm_cancel_"))
async def confirm_cancel_booking(callback_query: CallbackQuery, state: FSMContext, bot: Bot): # Добавили 'bot: Bot'
    booking_id = int(callback_query.data.split("_")[2])
    user_id = callback_query.from_user.id # Получаем user_id для get_main_menu_keyboard
    
    # Теперь cancel_booking возвращает (success, booking_details)
    success, booking_details = cancel_booking(booking_id) 

    if success:
        await callback_query.message.edit_text("✅ Ваша запись успешно отменена.", reply_markup=None)
        await callback_query.message.answer(
            "Что еще могу для вас сделать?", 
            reply_markup=get_main_menu_keyboard(user_id) # Передаем user_id
        )
        
        # --- ОТПРАВКА УВЕДОМЛЕНИЯ АДМИНУ ОБ ОТМЕНЕ ---
        if booking_details:
            # Разворачиваем полученные детали бронирования
            user_name, user_phone, service_name, booking_date_str, booking_time = booking_details
            
            # Форматируем дату для удобства чтения
            booking_date_obj = datetime.strptime(booking_date_str, '%Y-%m-%d')
            formatted_booking_date = booking_date_obj.strftime('%d.%m.%Y')

            admin_notification_text = (
                f"🚫 **Отмена бронирования!**\n\n"
                f"👤 Пользователь: {user_name} (TG ID: `{callback_query.from_user.id}`)\n"
                f"📞 Телефон: `{user_phone if user_phone else 'Не указан'}`\n"
                f"✨ Услуга: **{service_name}**\n"
                f"🗓 Дата: **{formatted_booking_date}**\n"
                f"⏰ Время: **{booking_time}**\n"
                f"ID брони: `{booking_id}`"
            )
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, admin_notification_text, parse_mode="Markdown")
                    logger.info(f"Уведомление об отмене брони {booking_id} отправлено админу {admin_id}")
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление об отмене брони {booking_id} админу {admin_id}: {e}")
        # --- КОНЕЦ УВЕДОМЛЕНИЯ АДМИНУ ---
        
    else:
        await callback_query.message.edit_text("❌ Не удалось отменить запись. Возможно, она уже отменена или не существует.", reply_markup=None)
        await callback_query.message.answer(
            "Что еще могу для вас сделать?", 
            reply_markup=get_main_menu_keyboard(user_id) # Передаем user_id
        )

    await state.clear()
    await callback_query.answer()

@user_router.callback_query(F.data == "back_to_my_bookings")
async def back_to_my_bookings_handler(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.delete()
    await show_my_bookings(callback_query.message, state)
    await callback_query.answer()

@user_router.message(F.text == "📜 История записей")
async def show_booking_history(message: Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Пожалуйста, начните с команды /start.")
        return

    history = get_user_booking_history(user[0])
    if history:
        history_text = "<b>Ваша история записей:</b>\n\n"
        # Словарь для перевода статусов
        status_translations = {
            "completed": "завершена",
            "cancelled": "отменена",
            "active": "активна" # Хотя 'active' не должен появляться в истории, лучше его тоже перевести
        }
        # Словарь для эмодзи
        status_emojis = {
            "completed": "✅",
            "cancelled": "❌",
            "active": "🔄"
        }

        for booking_id, service_name, duration_min, booking_date, booking_time, status in history:
            translated_status = status_translations.get(status, status) # Получаем перевод, если есть
            status_emoji = status_emojis.get(status, "❓") # Получаем эмодзи

            history_text += (
                f"{status_emoji} Услуга: <b>{service_name}</b> ({duration_min} мин.)\n"
                f"   Дата: <b>{datetime.strptime(booking_date, '%Y-%m-%d').strftime('%d.%m.%Y')}</b>\n"
                f"   Время: <b>{booking_time}</b>\n"
                f"   Статус: <i>{translated_status}</i>\n\n" # Используем переведенный статус
            )
        await message.answer(history_text, parse_mode="HTML")
    else:
        await message.answer("У вас пока нет записей в истории.")

@user_router.message(F.text == "✉️ Сообщить об опоздании")
async def report_late(message: Message, bot: Bot):
    """
    Позволяет пользователю сообщить об опоздании.
    Отправляет уведомление администраторам.
    """
    user_tg_id = message.from_user.id
    user_info = get_user(user_tg_id)

    if not user_info:
        await message.answer("Вы не зарегистрированы. Пожалуйста, начните с команды /start.")
        return

    booking_details = get_user_active_booking_full_details(user_tg_id)

    if booking_details:
        _, _, user_name, user_phone, service_name, _, booking_date_str, booking_time_str = booking_details

        formatted_date = datetime.strptime(booking_date_str, "%Y-%m-%d").strftime("%d.%m.%Y")

        admin_message = (
            f"❗️ **Сообщение об опоздании**\n\n"
            f"**Пользователь:** {user_name} (TG ID: `{user_tg_id}`)\n"
            f"**Телефон:** {user_phone if user_phone else 'Не указан'}\n"
            f"**Услуга:** {service_name}\n"
            f"**Дата записи:** {formatted_date}\n"
            f"**Время записи:** {booking_time_str}\n\n"
            f"Пользователь сообщает, что может опоздать на свою запись."
        )

        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(chat_id=admin_id, text=admin_message, parse_mode="Markdown")
            except Exception as e:
                print(f"Не удалось отправить сообщение админу {admin_id}: {e}")
        
        await message.answer("✅ Ваше сообщение об опоздании отправлено администраторам. Спасибо!")
    else:
        await message.answer("У вас нет активных записей, чтобы сообщить об опоздании.")

@user_router.message(F.text == "Отмена", StateFilter("*"))
async def handle_cancel_button(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Сейчас нет активных операций для отмены.", reply_markup=get_main_menu_keyboard())
        return

    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_main_menu_keyboard())

@user_router.message(StateFilter(None), F.text)
async def handle_unknown_text(message: Message):
    await message.answer(
        "Извините, я не понял вашу команду. Пожалуйста, выберите действие из меню "
        "или используйте команду /start для начала работы.",
        reply_markup=get_main_menu_keyboard()
    )