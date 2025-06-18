# project/factories.py
from aiogram.filters.callback_data import CallbackData

class AdminCallbackFactory(CallbackData, prefix="admin"):
    action: str
    service_id: int | None = None
    date: str | None = None
    booking_id: int | None = None
    # ... другие поля

class UserCallbackFactory(CallbackData, prefix="user"):
    action: str
    booking_id: int | None = None
    date: str | None = None
    time: str | None = None
    # ... другие поля

class CalendarCallbackFactory(CallbackData, prefix="calendar"):
    action: str  # 'select_date', 'prev_month', 'next_month' и т.д.
    year: int | None = None
    month: int | None = None
    day: int | None = None
    date: str | None = None # Для выбранной даты
    # ... другие поля