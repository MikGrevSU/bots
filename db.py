import sqlite3
import os
import uuid
from datetime import datetime, timedelta

DATABASE_NAME = 'bookings.db'

def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone_number TEXT UNIQUE
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            duration_min INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            booking_time TEXT NOT NULL,
            status TEXT DEFAULT 'active', -- 'active', 'completed', 'cancelled'
            notified INTEGER DEFAULT 0, -- 0 for not notified, 1 for notified <--- НОВОЕ ПОЛЕ
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)
    conn.commit()
    conn.close()
    print(f"База данных '{DATABASE_NAME}' инициализирована.")


# --- Функции для работы с пользователями (users) ---

def add_user(telegram_id: int, name: str, phone_number: str):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (telegram_id, name, phone_number) VALUES (?, ?, ?)",
                       (telegram_id, name, phone_number))
        conn.commit()
        # !!! ВАЖНО: ВОЗВРАЩАЕМ КОРТЕЖ (БУЛЕВО ЗНАЧЕНИЕ, ID ПОЛЬЗОВАТЕЛЯ) !!!
        return True, cursor.lastrowid
    except sqlite3.IntegrityError:
        # Если пользователь с таким telegram_id уже существует
        # !!! ВАЖНО: ВОЗВРАЩАЕМ КОРТЕЖ (БУЛЕВО ЗНАЧЕНИЕ, СООБЩЕНИЕ ОБ ОШИБКЕ) !!!
        return False, "Пользователь с таким Telegram ID уже существует."
    except Exception as e:
        # В случае любой другой неожиданной ошибки
        # !!! ВАЖНО: ВОЗВРАЩАЕМ КОРТЕЖ (БУЛЕВО ЗНАЧЕНИЕ, СООБЩЕНИЕ ОБ ОШИБКЕ) !!!
        return False, f"Ошибка при добавлении пользователя: {e}"
    finally:
        # Важно закрывать соединение в любом случае
        conn.close()

def get_all_users():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, telegram_id, name, phone_number FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# --- НОВАЯ/ОБНОВЛЕННАЯ ФУНКЦИЯ ДЛЯ РЕДАКТИРОВАНИЯ УСЛУГИ ---
def update_service(service_id: int, field_name: str, new_value):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # Проверка field_name для предотвращения SQL-инъекций
        if field_name not in ['name', 'price', 'duration_min']:
            return False, "Недопустимое поле для обновления."

        if field_name == 'name':
            cursor.execute(f"UPDATE services SET {field_name} = ? WHERE id = ?", (new_value, service_id))
        elif field_name == 'price':
            cursor.execute(f"UPDATE services SET {field_name} = ? WHERE id = ?", (float(new_value), service_id))
        elif field_name == 'duration_min':
            cursor.execute(f"UPDATE services SET {field_name} = ? WHERE id = ?", (int(new_value), service_id))

        conn.commit()
        return True, "Услуга успешно обновлена."
    except sqlite3.IntegrityError:
        return False, "Услуга с таким названием уже существует." # Для поля name
    except ValueError:
        return False, "Неверный формат нового значения (ожидалось число)."
    except Exception as e:
        return False, f"Ошибка при обновлении услуги: {e}"
    finally:
        conn.close()

def get_all_bookings_in_system():
    """
    Возвращает все бронирования в системе.
    Возвращает: список кортежей (booking_id, user_telegram_id, user_name, user_phone_number, service_name, service_duration, booking_date, booking_time, status)
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            b.id,
            u.telegram_id,
            u.name,
            u.phone_number,
            s.name,
            s.duration_min,
            b.booking_date,
            b.booking_time,
            b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN services s ON b.service_id = s.id
        ORDER BY b.booking_date DESC, b.booking_time DESC
    """)
    bookings = cursor.fetchall()
    conn.close()
    return bookings

def get_user(telegram_id: int):
    """Получает данные пользователя по его Telegram ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, telegram_id, name, phone_number FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(telegram_id: int, name: str = None, phone_number: str = None):
    """Обновляет данные пользователя по его Telegram ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    updates = []
    params = []
    if name:
        updates.append("name = ?")
        params.append(name)
    if phone_number:
        updates.append("phone_number = ?")
        params.append(phone_number)

    if not updates:
        conn.close()
        return False

    query = f"UPDATE users SET {', '.join(updates)} WHERE telegram_id = ?"
    params.append(telegram_id)

    cursor.execute(query, tuple(params))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# --- Функции для работы с услугами (services) ---

def add_service(name: str, price: float, duration_min: int):
    """
    Добавляет новую услугу в базу данных.
    Возвращает (True, "Успешно") в случае успеха, (False, "Сообщение об ошибке") в случае ошибки.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Проверка на существование услуги с таким же именем
    cursor.execute("SELECT id FROM services WHERE name = ?", (name,))
    if cursor.fetchone():
        conn.close()
        return False, "Услуга с таким названием уже существует."

    try:
        cursor.execute("INSERT INTO services (name, price, duration_min) VALUES (?, ?, ?)",
                       (name, price, duration_min))
        conn.commit()
        return True, "Услуга успешно добавлена."
    except sqlite3.Error as e:
        print(f"Database error adding service: {e}") # Для отладки
        return False, f"Ошибка базы данных: {e}"
    except Exception as e:
        print(f"Unexpected error adding service: {e}") # Для отладки
        return False, f"Непредвиденная ошибка: {e}"
    finally:
        conn.close()

def get_service(service_id: int = None, service_name: str = None):
    """Получает информацию об услуге по ID или имени."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    if service_id:
        cursor.execute("SELECT id, name, price, duration_min FROM services WHERE id = ?", (service_id,))
    elif service_name:
        cursor.execute("SELECT id, name, price, duration_min FROM services WHERE name = ?", (service_name,))
    else:
        conn.close()
        return None
    service = cursor.fetchone()
    conn.close()
    return service

def get_all_services():
    """Получает список всех доступных услуг."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, duration_min FROM services ORDER BY name")
    services = cursor.fetchall()
    conn.close()
    return services

def edit_service(service_id: int, name: str = None, price: float = None, duration_min: int = None):
    """Изменяет данные существующей услуги."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    updates = []
    params = []
    if name:
        updates.append("name = ?")
        params.append(name)
    if price is not None: # Может быть 0
        updates.append("price = ?")
        params.append(price)
    if duration_min is not None: # Может быть 0
        updates.append("duration_min = ?")
        params.append(duration_min)

    if not updates:
        conn.close()
        return False

    query = f"UPDATE services SET {', '.join(updates)} WHERE id = ?"
    params.append(service_id)

    try:
        cursor.execute(query, tuple(params))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        # Новое имя услуги уже существует
        return False
    finally:
        conn.close()

def delete_service(service_id: int):
    """Удаляет услугу по её ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM services WHERE id = ?", (service_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


# --- Функции для работы с записями (bookings) ---

def get_free_slots(booking_date_str: str, service_duration: int, start_time_str="09:00", end_time_str="18:00"):
    """
    Генерирует список свободных временных слотов на заданную дату,
    учитывая длительность услуги и уже существующие бронирования.
    Шаг генерации слотов равен длительности самой услуги.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Получаем все активные брони на выбранную дату
    cursor.execute("""
        SELECT b.booking_time, s.duration_min
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.booking_date = ? AND b.status = 'active'
    """, (booking_date_str,))
    booked_slots_raw = cursor.fetchall()
    conn.close()

    booked_intervals = []
    for booked_time_str, booked_duration in booked_slots_raw:
        booked_start_dt = datetime.strptime(f"{booking_date_str} {booked_time_str}", "%Y-%m-%d %H:%M")
        booked_end_dt = booked_start_dt + timedelta(minutes=booked_duration)
        booked_intervals.append((booked_start_dt, booked_end_dt))

    start_datetime_limit = datetime.strptime(f"{booking_date_str} {start_time_str}", "%Y-%m-%d %H:%M")
    end_datetime_limit = datetime.strptime(f"{booking_date_str} {end_time_str}", "%Y-%m-%d %H:%M")

    available_slots = []
    
    current_time = datetime.now()
    today_date_obj = datetime.strptime(booking_date_str, "%Y-%m-%d").date()

    if today_date_obj == current_time.date():
        # Если сегодня, то начальный слот должен быть позже текущего времени
        # Выравниваем текущее время до ближайшего следующего кратного service_duration
        # относительно начала рабочего дня (start_datetime_limit)
        
        # Разница в минутах от начала рабочего дня до текущего момента
        minutes_since_start_of_day = (current_time - start_datetime_limit).total_seconds() / 60
        
        if minutes_since_start_of_day < 0: # Если текущее время раньше начала рабочего дня
            current_slot_start = start_datetime_limit
        else:
            # Сколько 'service_duration' интервалов прошло с начала рабочего дня
            intervals_passed = int(minutes_since_start_of_day / service_duration)
            
            # Предполагаемое время начала следующего интервала
            next_interval_start = start_datetime_limit + timedelta(minutes=(intervals_passed * service_duration))
            
            # Если текущее время уже после предполагаемого начала интервала,
            # то нужно перейти к следующему интервалу
            if current_time > next_interval_start:
                next_interval_start += timedelta(minutes=service_duration)
            
            current_slot_start = next_interval_start.replace(second=0, microsecond=0)
            
            # Убеждаемся, что мы не стартуем раньше начала рабочего дня
            current_slot_start = max(start_datetime_limit, current_slot_start)

    else: # Если дата в будущем, начинаем с начала рабочего дня
        current_slot_start = start_datetime_limit
    
    # Основной цикл генерации слотов
    while current_slot_start + timedelta(minutes=service_duration) <= end_datetime_limit:
        slot_is_free = True
        current_slot_end = current_slot_start + timedelta(minutes=service_duration)

        for booked_start, booked_end in booked_intervals:
            # Проверка на пересечение интервалов [current_slot_start, current_slot_end)
            # и [booked_start, booked_end)
            if not (current_slot_end <= booked_start or current_slot_start >= booked_end):
                slot_is_free = False
                break

        if slot_is_free:
            available_slots.append(current_slot_start.strftime("%H:%M"))

        # Переходим к следующему потенциальному началу слота с шагом, равным длительности услуги
        current_slot_start += timedelta(minutes=service_duration) # <--- ГЛАВНОЕ ИЗМЕНЕНИЕ ЗДЕСЬ!

    return available_slots

def create_booking(user_id: int, service_id: int, booking_date: str, booking_time: str):
    """
    Создает новую запись в БД.
    Возвращает True в случае успеха, False если у пользователя уже есть активная бронь
    или если слот уже занят.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Проверка на 1 активную бронь у пользователя
    cursor.execute("SELECT id FROM bookings WHERE user_id = ? AND status = 'active'", (user_id,))
    if cursor.fetchone():
        conn.close()
        return False, "У вас уже есть активная запись. Отмените её, чтобы сделать новую."

    # Проверка доступности слота
    service = get_service(service_id=service_id)
    if not service:
        conn.close()
        return False, "Выбранная услуга не найдена."

    service_duration = service[3] # duration_min

    # Дополнительная проверка на занятость слота
    # Для этого получаем все занятые слоты на эту дату и проверяем, не попадает ли наша запись в них
    # Этот шаг по сути дублирует логику get_free_slots, но выполняется непосредственно перед вставкой
    # для предотвращения race conditions.
    all_booked_on_date = []
    cursor.execute("""
        SELECT b.booking_time, s.duration_min
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.booking_date = ? AND b.status = 'active'
    """, (booking_date,))
    for booked_time_str, booked_duration in cursor.fetchall():
        booked_start_dt = datetime.strptime(f"{booking_date} {booked_time_str}", "%Y-%m-%d %H:%M")
        booked_end_dt = booked_start_dt + timedelta(minutes=booked_duration)
        all_booked_on_date.append((booked_start_dt, booked_end_dt))

    new_booking_start_dt = datetime.strptime(f"{booking_date} {booking_time}", "%Y-%m-%d %H:%M")
    new_booking_end_dt = new_booking_start_dt + timedelta(minutes=service_duration)

    for booked_start, booked_end in all_booked_on_date:
        if not (new_booking_end_dt <= booked_start or new_booking_start_dt >= booked_end):
            conn.close()
            return False, "Выбранное время уже занято. Пожалуйста, выберите другой слот."

    try:
        cursor.execute("INSERT INTO bookings (user_id, service_id, booking_date, booking_time, status) VALUES (?, ?, ?, ?, ?)",
                       (user_id, service_id, booking_date, booking_time, 'active'))
        conn.commit()
        return True, "Запись успешно создана!"
    except Exception as e:
        conn.rollback()
        return False, f"Произошла ошибка при создании записи: {e}"
    finally:
        conn.close()


# def cancel_booking(booking_id: int):
#     """Отменяет запись по её ID."""
#     conn = sqlite3.connect(DATABASE_NAME)
#     cursor = conn.cursor()
#     cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
#     conn.commit()
#     conn.close()
#     return cursor.rowcount > 0
        

def cancel_booking(booking_id: int):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        # 1. Получаем детали бронирования СТРОГО с активным статусом
        cursor.execute("""
            SELECT 
                u.name, 
                u.phone_number, 
                s.name, 
                b.booking_date, 
                b.booking_time
            FROM bookings b
            JOIN users u ON b.user_id = u.id  -- ИЗМЕНЕНО ЗДЕСЬ: b.user_id = u.id
            JOIN services s ON b.service_id = s.id
            WHERE b.id = ? AND b.status = 'active'
        """, (booking_id,))
        booking_details = cursor.fetchone()

        if booking_details:
            # 2. Если бронь найдена и активна, тогда обновляем её статус
            cursor.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
            conn.commit()
            print(f"DEBUG: Бронирование {booking_id} успешно отменено в БД.")
            return True, booking_details
        else:
            print(f"DEBUG: Бронирование {booking_id} не найдено или неактивно.")
            return False, None 
    except Exception as e:
        print(f"DEBUG: Ошибка в cancel_booking (db.py): {e}")
        return False, None
    finally:
        conn.close()
        
def get_user_active_booking(user_id: int):
    """Получает активную запись пользователя."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, s.name, s.duration_min, b.booking_date, b.booking_time
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.user_id = ? AND b.status = 'active'
    """, (user_id,))
    booking = cursor.fetchone()
    conn.close()
    return booking

def get_user_active_booking_full_details(user_telegram_id: int):
    """
    Получает полную информацию об активной записи пользователя по его Telegram ID,
    включая данные пользователя и услуги.
    Возвращает кортеж: (booking_id, user_telegram_id, user_name, user_phone_number, service_name, service_duration, booking_date, booking_time)
    или None, если активной записи нет.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            b.id,
            u.telegram_id,
            u.name,
            u.phone_number,
            s.name,
            s.duration_min,
            b.booking_date,
            b.booking_time
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN services s ON b.service_id = s.id
        WHERE u.telegram_id = ? AND b.status = 'active'
    """, (user_telegram_id,))
    booking_details = cursor.fetchone()
    conn.close()
    return booking_details


def get_user_booking_history(user_id: int):
    """Получает историю записей пользователя (все, кроме активной)."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, s.name, s.duration_min, b.booking_date, b.booking_time, b.status
        FROM bookings b
        JOIN services s ON b.service_id = s.id
        WHERE b.user_id = ? AND b.status != 'active'
        ORDER BY b.booking_date DESC, b.booking_time DESC
    """, (user_id,))
    history = cursor.fetchall()
    conn.close()
    return history

def get_all_bookings_for_date(target_date: str):
    """
    Возвращает все бронирования на указанную дату, включая информацию о пользователе и услуге.
    target_date: Дата в формате 'YYYY-MM-DD'.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            b.id,              -- 1 (booking_id)
            u.telegram_id,     -- 2 (tg_id)
            u.name,            -- 3 (user_name)
            u.phone_number,    -- 4 (user_phone)
            s.name,            -- 5 (service_name)
            s.duration_min,    -- 6 (service_duration)
            b.booking_date,    -- 7 (booking_date)
            b.booking_time,    -- 8 (booking_time)
            b.status,          -- 9 (status)
            b.notified         -- 10 (notified)
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN services s ON b.service_id = s.id
        WHERE b.booking_date = ?
        ORDER BY b.booking_time
    """, (target_date,))
    bookings = cursor.fetchall()
    conn.close()
    return bookings

def get_all_bookings_for_service(service_id: int):
    """Получает все записи для определенной услуги."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, u.name, u.phone_number, b.booking_date, b.booking_time, b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.service_id = ?
        ORDER BY b.booking_date, b.booking_time
    """, (service_id,))
    bookings = cursor.fetchall()
    conn.close()
    return bookings

def get_booking_details(booking_id: int):
    """Получает полную информацию о записи по её ID."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, u.telegram_id, u.name, u.phone_number, s.name, s.duration_min, b.booking_date, b.booking_time, b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN services s ON b.service_id = s.id
        WHERE b.id = ?
    """, (booking_id,))
    booking = cursor.fetchone()
    conn.close()
    return booking

def get_all_bookings():
    """Получает все записи из базы данных."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, u.telegram_id, u.name, u.phone_number, s.name, s.duration_min, b.booking_date, b.booking_time, b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN services s ON b.service_id = s.id
        ORDER BY b.booking_date DESC, b.booking_time DESC
    """)
    all_bookings = cursor.fetchall()
    conn.close()
    return all_bookings

if __name__ == "__main__":
    # Пример использования функций (для тестирования)
    init_db()
    print("DB initialized. Adding some test data...")

    # Добавление пользователей
    add_user(12345, "Иван Иванов", "+79123456789")
    add_user(67890, "Мария Петрова") # Без телефона
    add_user(11223, "Админ Бот", "+79001112233") # Для проверки админской учетки

    # Обновление пользователя
    update_user(12345, phone_number="+79998887766")

    user_ivan = get_user(12345)
    print(f"User Ivan: {user_ivan}")

    # Добавление услуг
    add_service("Стрижка мужская", 1000, 45)
    add_service("Стрижка женская", 1500, 60)
    add_service("Бритье бороды", 700, 30)

    services = get_all_services()
    print(f"All services: {services}")
    service_beard = get_service(service_name="Бритье бороды")
    print(f"Service Beard: {service_beard}")

    # Редактирование услуги
    edit_service(service_id=service_beard[0], price=750)
    service_beard_updated = get_service(service_name="Бритье бороды")
    print(f"Service Beard Updated: {service_beard_updated}")


    # Проверка свободных слотов
    today_date = datetime.now().strftime("%Y-%m-%d")
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"\nFree slots for 'Стрижка мужская' ({service_beard_updated[3]} min) on {today_date}:")
    free_slots = get_free_slots(today_date, service_beard_updated[3])
    print(free_slots)

    # Создание записи
    # Получаем user_id для Ивана и service_id для "Стрижка мужская"
    user_id_ivan = get_user(12345)[0]
    service_id_man_cut = get_service(service_name="Стрижка мужская")[0]

    if free_slots:
        chosen_time = free_slots[0] # Выбираем первый свободный слот
        success, message = create_booking(user_id_ivan, service_id_man_cut, today_date, chosen_time)
        print(f"\nBooking attempt 1: {message}")
        if success:
            print(f"Booking created for {today_date} at {chosen_time}")

            # Попытка создать вторую активную бронь (должно быть отказано)
            success_2, message_2 = create_booking(user_id_ivan, service_id_man_cut, today_date, free_slots[1] if len(free_slots) > 1 else "10:00")
            print(f"Booking attempt 2 (should fail for user): {message_2}")

            # Просмотр активной брони пользователя
            active_booking = get_user_active_booking(user_id_ivan)
            print(f"\nUser Ivan's active booking: {active_booking}")

            # Отмена брони
            if active_booking:
                cancel_success = cancel_booking(active_booking[0])
                print(f"Booking cancelled: {cancel_success}")
                print(f"User Ivan's active booking after cancel: {get_user_active_booking(user_id_ivan)}")

            # Создание еще одной брони для истории
            create_booking(user_id_ivan, service_id_man_cut, tomorrow_date, "10:00")
            cancel_booking(get_user_active_booking(user_id_ivan)[0]) # Отменяем для истории

            # Просмотр истории бронирований
            history = get_user_booking_history(user_id_ivan)
            print(f"\nUser Ivan's booking history: {history}")

    # Получение всех броней на дату
    print(f"\nAll bookings for {today_date}:")
    all_bookings_today = get_all_bookings_for_date(today_date)
    for booking in all_bookings_today:
        print(booking)

    # Получение всех броней по услуге
    service_id_female_cut = get_service(service_name="Стрижка женская")[0]
    print(f"\nAll bookings for 'Стрижка женская':")
    all_bookings_female_cut = get_all_bookings_for_service(service_id_female_cut)
    for booking in all_bookings_female_cut:
        print(booking)

    # Получение всех броней в системе
    print("\nAll bookings in system:")
    all_system_bookings = get_all_bookings()
    for booking in all_system_bookings:
        print(booking)

    # Удаление услуги (после всех тестов с ней, чтобы не сломать зависимости)
    # delete_service(service_id_man_cut)
    # print(f"Service 'Стрижка мужская' deleted: {get_service(service_id=service_id_man_cut)}")


def get_bookings_for_notification(time_delta_minutes=30):
    """
    Возвращает список активных бронирований, которые должны начаться
    через time_delta_minutes, и по которым еще не было отправлено уведомление.
    Возвращает: [(booking_id, user_telegram_id, service_name, booking_date, booking_time)]
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    current_datetime = datetime.now()
    
    # Расчет времени начала для поиска
    # Ищем записи, которые начнутся в интервале [current_datetime, current_datetime + time_delta_minutes + 1 минута]
    # Используем current_datetime.strftime('%H:%M:%S') для более точного сравнения времени,
    # но SQLite хранит время в HH:MM, поэтому будем сравнивать минуты в Python.
    
    # Получаем все активные бронирования, которые еще не были уведомлены
    # и дата которых совпадает с сегодняшней или будущей
    cursor.execute("""
        SELECT
            b.id,
            u.telegram_id,
            s.name,
            b.booking_date,
            b.booking_time,
            s.duration_min -- Добавляем длительность, чтобы более точно рассчитать конец слота
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        JOIN services s ON b.service_id = s.id
        WHERE b.status = 'active' AND b.notified = 0
    """)
    
    upcoming_bookings = []
    for booking_id, telegram_id, service_name, booking_date_str, booking_time_str, duration_min in cursor.fetchall():
        booking_datetime = datetime.strptime(f"{booking_date_str} {booking_time_str}", "%Y-%m-%d %H:%M")
        
        # Разница между текущим временем и временем начала бронирования
        time_until_booking = booking_datetime - current_datetime
        if timedelta(minutes=0) <= time_until_booking <= timedelta(minutes=time_delta_minutes + 1, seconds=5): # Добавим небольшой буфер
            upcoming_bookings.append((booking_id, telegram_id, service_name, booking_date_str, booking_time_str))
            
    conn.close()
    return upcoming_bookings

def mark_booking_notified(booking_id: int):
    """Отмечает бронирование как уведомленное."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE bookings SET notified = 1 WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()