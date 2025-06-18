# project/states.py
from aiogram.fsm.state import State, StatesGroup

class UserRegistration(StatesGroup):
    """Состояния для регистрации нового пользователя."""
    waiting_for_name = State()
    waiting_for_phone = State()

class UserBooking(StatesGroup):
    """Состояния для процесса бронирования услуги."""
    waiting_for_service = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirmation = State()

class UserAdmin(StatesGroup):
    """Состояния для административных функций."""
    admin_main_menu = State()
    # Управление услугами
    add_service_name = State()
    add_service_price = State()
    add_service_duration = State()
    edit_service_select = State()
    edit_service_name = State()
    edit_service_price = State()
    edit_service_duration = State()
    delete_service_select = State()
    # Управление бронированиями
    manage_bookings_select_date = State()
    manage_bookings_select_service = State()
    add_booking_user_tgid = State()
    add_booking_service = State()
    add_booking_date = State()
    add_booking_time = State()
    cancel_booking_select = State()