# utils/time_slots.py
from datetime import datetime, timedelta

WORKING_HOURS_START = 9  # 9:00 AM
WORKING_HOURS_END = 18   # 6:00 PM (18:00)
TIME_SLOT_INTERVAL_MINUTES = 30 # Интервал между доступными слотами

def get_available_time_slots(date_str: str, service_duration_minutes: int, booked_slots_data: list):
    """
    Генерирует список доступных временных слотов для указанной даты и длительности услуги,
    учитывая уже забронированные слоты.

    Args:
        date_str (str): Дата в формате 'YYYY-MM-DD'.
        service_duration_minutes (int): Длительность выбранной услуги в минутах.
        booked_slots_data (list): Список кортежей (время_начала_бронирования, длительность_бронирования)
                                  для уже занятых слотов на эту дату.
                                  Пример: [('10:00', 60), ('11:30', 90)]

    Returns:
        list: Список строк с доступными временными слотами в формате 'HH:MM'.
    """
    available_slots = []
    
    # Конвертируем забронированные слоты в интервалы datetime
    booked_intervals = []
    for booked_time_str, booked_duration in booked_slots_data:
        booked_start = datetime.strptime(f"{date_str} {booked_time_str}", "%Y-%m-%d %H:%M")
        booked_end = booked_start + timedelta(minutes=booked_duration)
        booked_intervals.append((booked_start, booked_end))

    current_time_dt = datetime.strptime(f"{date_str} {WORKING_HOURS_START:02d}:00", "%Y-%m-%d %H:%M")
    end_of_day_dt = datetime.strptime(f"{date_str} {WORKING_HOURS_END:02d}:00", "%Y-%m-%d %H:%M")

    while current_time_dt + timedelta(minutes=service_duration_minutes) <= end_of_day_dt:
        slot_end_time = current_time_dt + timedelta(minutes=service_duration_minutes)
        is_available = True

        # Проверяем пересечение с каждой забронированной записью
        for booked_start, booked_end in booked_intervals:
            # Пересечение интервалов:
            # (start1 < end2) and (end1 > start2)
            if (current_time_dt < booked_end) and (slot_end_time > booked_start):
                is_available = False
                break

        if is_available:
            available_slots.append(current_time_dt.strftime("%H:%M"))

        current_time_dt += timedelta(minutes=TIME_SLOT_INTERVAL_MINUTES)
    
    return available_slots

# Тестирование модуля time_slots
if __name__ == '__main__':
    today_str = datetime.now().strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Пример забронированных слотов для тестирования
    test_booked_slots_today = [
        ('10:00', 60),  # Забронировано с 10:00 до 11:00
        ('14:30', 90)   # Забронировано с 14:30 до 16:00
    ]

    print(f"Текущая дата: {today_str}")

    print("\nДоступные слоты для услуги 30 минут (без бронирований):")
    slots_30_min_no_booking = get_available_time_slots(today_str, 30, [])
    print(slots_30_min_no_booking)

    print("\nДоступные слоты для услуги 60 минут (с тестовыми бронированиями):")
    slots_60_min = get_available_time_slots(today_str, 60, test_booked_slots_today)
    print(slots_60_min)

    print("\nДоступные слоты для услуги 90 минут (с тестовыми бронированиями):")
    slots_90_min = get_available_time_slots(today_str, 90, test_booked_slots_today)
    print(slots_90_min)

    print("\nДоступные слоты для услуги 120 минут (с тестовыми бронированиями):")
    slots_120_min = get_available_time_slots(today_str, 120, test_booked_slots_today)
    print(slots_120_min)

    print("\nДоступные слоты для завтрашней даты (без бронирований):")
    slots_tomorrow = get_available_time_slots(tomorrow_str, 60, [])
    print(slots_tomorrow)