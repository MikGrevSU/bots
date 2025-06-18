import aiosqlite
import datetime
from typing import List, Dict, Tuple, Optional

class DBManager:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.conn = None # Инициализируем соединение как None

    async def connect(self):
        """Устанавливает соединение с базой данных."""
        if self.conn is None: # Подключаемся только если соединение еще не установлено
            self.conn = await aiosqlite.connect(self.db_name)
            self.conn.row_factory = aiosqlite.Row # Для доступа к колонкам по имени
            await self.conn.execute("PRAGMA foreign_keys = ON;") # Включаем поддержку внешних ключей

    async def init_db(self):
        """
        Инициализирует базу данных: устанавливает соединение и создает таблицы,
        если они еще не существуют.
        """
        await self.connect() # Убеждаемся, что соединение установлено
        await self.create_tables()

    async def close(self):
        """Закрывает соединение с базой данных."""
        if self.conn: # Закрываем только если соединение существует
            await self.conn.close()
            self.conn = None # Сбрасываем соединение

    async def _execute(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Cursor]:
        """Вспомогательный метод для выполнения запросов."""
        if self.conn is None:
            # Если соединение не установлено (что не должно произойти после init_db),
            # вы можете либо подключиться, либо вывести ошибку.
            # Для надежности можно добавить await self.connect() здесь,
            # но init_db должен позаботиться об этом.
            print("Error: Database connection not established for _execute.")
            return None
        try:
            cursor = await self.conn.execute(query, params)
            await self.conn.commit()
            return cursor
        except aiosqlite.Error as e:
            print(f"Database error: {e}")
            return None

    async def create_tables(self):
        """Создает таблицы базы данных, если они не существуют."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                phone_number TEXT UNIQUE,
                telegram_id INTEGER UNIQUE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                address TEXT,
                description TEXT,
                working_hours_start TEXT NOT NULL, -- HH:MM
                working_hours_end TEXT NOT NULL,   -- HH:MM
                slot_duration_minutes INTEGER NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE, -- Связь с таблицей users
                location_id INTEGER,    -- FK, NULLABLE для супер-админа
                role TEXT NOT NULL,     -- 'super_admin', 'location_admin'
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS services (
                service_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL,
                duration_minutes INTEGER NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations (location_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                location_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                booking_date TEXT NOT NULL, -- YYYY-MM-DD
                booking_time TEXT NOT NULL, -- HH:MM
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (location_id) REFERENCES locations (location_id),
                FOREIGN KEY (service_id) REFERENCES services (service_id),
                UNIQUE(user_id, location_id, booking_date) -- Ограничение: 1 запись с одного номера на 1 организацию в 1 день
            );
            """
        ]
        for query in queries:
            await self._execute(query)

    # --- Управление пользователями/админами ---

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Возвращает пользователя по его Telegram ID."""
        cursor = await self._execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        return dict(user) if user else None

    async def add_user(self, telegram_id: int, phone_number: Optional[str] = None) -> Optional[int]:
        """Добавляет нового пользователя и возвращает его user_id."""
        cursor = await self._execute(
            "INSERT INTO users (telegram_id, phone_number) VALUES (?, ?)",
            (telegram_id, phone_number)
        )
        return cursor.lastrowid if cursor else None

    async def update_user_phone(self, user_id: int, phone_number: str) -> bool:
        """Обновляет номер телефона пользователя."""
        cursor = await self._execute(
            "UPDATE users SET phone_number = ? WHERE user_id = ?",
            (phone_number, user_id)
        )
        return cursor.rowcount > 0 if cursor else False

    async def get_admin_by_user_id(self, user_id: int) -> Optional[dict]:
        """Возвращает данные админа по user_id."""
        cursor = await self._execute("SELECT * FROM admins WHERE user_id = ?", (user_id,))
        admin = await cursor.fetchone()
        return dict(admin) if admin else None

    async def add_admin(self, user_id: int, role: str, location_id: Optional[int] = None) -> Optional[int]:
        """Добавляет нового админа."""
        cursor = await self._execute(
            "INSERT INTO admins (user_id, role, location_id) VALUES (?, ?, ?)",
            (user_id, role, location_id)
        )
        return cursor.lastrowid if cursor else None

    async def get_all_admins(self) -> List[dict]:
        """Возвращает список всех админов."""
        cursor = await self._execute("SELECT a.*, u.telegram_id, l.name as location_name FROM admins a JOIN users u ON a.user_id = u.user_id LEFT JOIN locations l ON a.location_id = l.location_id")
        return [dict(row) for row in await cursor.fetchall()]

    # --- Управление организациями ---

    async def add_location(self, name: str, address: str, description: str,
                           working_hours_start: str, working_hours_end: str,
                           slot_duration_minutes: int) -> Optional[int]:
        """Добавляет новую организацию."""
        cursor = await self._execute(
            "INSERT INTO locations (name, address, description, working_hours_start, working_hours_end, slot_duration_minutes) VALUES (?, ?, ?, ?, ?, ?)",
            (name, address, description, working_hours_start, working_hours_end, slot_duration_minutes)
        )
        return cursor.lastrowid if cursor else None

    async def get_all_locations(self) -> List[dict]:
        """Возвращает список всех организаций."""
        cursor = await self._execute("SELECT * FROM locations")
        return [dict(row) for row in await cursor.fetchall()]

    async def get_location_by_id(self, location_id: int) -> Optional[dict]:
        """Возвращает организацию по ID."""
        cursor = await self._execute("SELECT * FROM locations WHERE location_id = ?", (location_id,))
        location = await cursor.fetchone()
        return dict(location) if location else None

    # --- Управление услугами ---

    async def add_service(self, location_id: int, name: str, price: float, duration_minutes: int) -> Optional[int]:
        """Добавляет новую услугу для организации."""
        cursor = await self._execute(
            "INSERT INTO services (location_id, name, price, duration_minutes) VALUES (?, ?, ?, ?)",
            (location_id, name, price, duration_minutes)
        )
        return cursor.lastrowid if cursor else None

    async def get_services_by_location(self, location_id: int) -> List[dict]:
        """Возвращает список услуг для указанной организации."""
        cursor = await self._execute("SELECT * FROM services WHERE location_id = ?", (location_id,))
        return [dict(row) for row in await cursor.fetchall()]

    async def get_service_by_id(self, service_id: int) -> Optional[dict]:
        """Возвращает услугу по ID."""
        cursor = await self._execute("SELECT * FROM services WHERE service_id = ?", (service_id,))
        service = await cursor.fetchone()
        return dict(service) if service else None

    async def delete_service(self, service_id: int) -> bool:
        """Удаляет услугу по ID."""
        cursor = await self._execute("DELETE FROM services WHERE service_id = ?", (service_id,))
        return cursor.rowcount > 0 if cursor else False

    # --- Управление записями (бронированиями) ---

    async def add_booking(self, user_id: int, location_id: int, service_id: int,
                            booking_date: str, booking_time: str) -> Optional[int]:
        """Добавляет новую запись."""
        # Проверка на дубликат (UNIQUE constraint в таблице bookings)
        try:
            cursor = await self._execute(
                "INSERT INTO bookings (user_id, location_id, service_id, booking_date, booking_time) VALUES (?, ?, ?, ?, ?)",
                (user_id, location_id, service_id, booking_date, booking_time)
            )
            return cursor.lastrowid if cursor else None
        except aiosqlite.IntegrityError:
            print(f"User {user_id} already has a booking for location {location_id} on {booking_date}")
            return None # Возвращаем None, если запись уже существует

    async def get_user_bookings(self, user_id: int) -> List[dict]:
        """Возвращает все предстоящие записи пользователя."""
        today = datetime.date.today().isoformat()
        current_time = datetime.datetime.now().strftime('%H:%M')
        
        # Записи на сегодня, но только те, время которых еще не прошло,
        # и записи на будущие дни
        query = """
            SELECT b.*, l.name as location_name, s.name as service_name
            FROM bookings b
            JOIN locations l ON b.location_id = l.location_id
            JOIN services s ON b.service_id = s.service_id
            WHERE b.user_id = ? AND (b.booking_date > ? OR (b.booking_date = ? AND b.booking_time >= ?))
            ORDER BY b.booking_date, b.booking_time;
        """
        cursor = await self._execute(query, (user_id, today, today, current_time))
        return [dict(row) for row in await cursor.fetchall()]

    async def get_location_bookings_for_date(self, location_id: int, date: str) -> List[dict]:
        """Возвращает все записи для организации на конкретную дату."""
        query = """
            SELECT b.*, u.phone_number, s.name as service_name
            FROM bookings b
            JOIN users u ON b.user_id = u.user_id
            JOIN services s ON b.service_id = s.service_id
            WHERE b.location_id = ? AND b.booking_date = ?
            ORDER BY b.booking_time;
        """
        cursor = await self._execute(query, (location_id, date))
        return [dict(row) for row in await cursor.fetchall()]

    async def delete_booking(self, booking_id: int) -> bool:
        """Удаляет запись по ID."""
        cursor = await self._execute("DELETE FROM bookings WHERE booking_id = ?", (booking_id,))
        return cursor.rowcount > 0 if cursor else False

    # --- Логика генерации временных слотов ---

    async def get_available_slots(self, location_id: int, booking_date: str) -> List[str]:
        """
        Генерирует свободные временные слоты для данной организации на конкретную дату.
        """
        location = await self.get_location_by_id(location_id)
        if not location:
            return []

        start_time_str = location['working_hours_start']
        end_time_str = location['working_hours_end']
        slot_duration = location['slot_duration_minutes']

        start_hour, start_minute = map(int, start_time_str.split(':'))
        end_hour, end_minute = map(int, end_time_str.split(':'))

        current_date = datetime.date.fromisoformat(booking_date)
        today = datetime.date.today()
        now = datetime.datetime.now()

        available_slots = []
        current_slot_time = datetime.datetime(
            current_date.year, current_date.month, current_date.day,
            start_hour, start_minute
        )
        end_of_day = datetime.datetime(
            current_date.year, current_date.month, current_date.day,
            end_hour, end_minute
        )

        # Получаем все занятые слоты на эту дату
        booked_slots_data = await self.get_location_bookings_for_date(location_id, booking_date)
        # Преобразуем в set для быстрого поиска
        booked_times = {b['booking_time'] for b in booked_slots_data}

        while current_slot_time + datetime.timedelta(minutes=slot_duration) <= end_of_day:
            slot_str = current_slot_time.strftime('%H:%M')

            # Условие для будущих дат или для сегодняшнего дня, но с учетом текущего времени
            if current_date > today or \
               (current_date == today and current_slot_time >= now):
                
                if slot_str not in booked_times:
                    available_slots.append(slot_str)
            
            current_slot_time += datetime.timedelta(minutes=slot_duration)
        
        return available_slots

# Создаем единственный экземпляр DBManager, который будет использоваться во всем приложении
# Это важно, чтобы все части приложения работали с одним и тем же подключением к базе данных.
db = DBManager(db_name="zapster.db")