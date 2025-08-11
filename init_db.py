#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ThermoGrid - Скрипт инициализации базы данных
===========================================
Создает необходимые таблицы в базе данных ThermoGrid
"""

import sqlite3
import os
import logging
import argparse

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Запросы для создания таблиц
CREATE_TABLES_SQL = {
    "devices": """
    CREATE TABLE IF NOT EXISTS devices (
        id TEXT PRIMARY KEY,
        deviceName TEXT,
        firmware_version TEXT,
        network TEXT,
        ip_address TEXT,
        last_seen INTEGER,
        uptime_ms INTEGER,
        alarm_active INTEGER,
        alarm_threshold_c REAL,
        lat REAL,
        lon REAL,
        raw_json TEXT
    )
    """,
    
    "sensors": """
    CREATE TABLE IF NOT EXISTS sensors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        sensor_id INTEGER,
        name TEXT,
        type TEXT,
        temperature REAL,
        humidity REAL,
        last_reading_time INTEGER,
        UNIQUE(device_id, sensor_id)
    )
    """,
    
    "readings": """
    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        sensor_id INTEGER,
        timestamp INTEGER,
        temperature_c REAL,
        humidity REAL
    )
    """
}

# Индексы для оптимизации запросов
CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_readings_device ON readings (device_id, sensor_id, timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_sensors_device ON sensors (device_id)",
    "CREATE INDEX IF NOT EXISTS idx_devices_last_seen ON devices (last_seen)"
]

def init_database(db_path, reset=False):
    """
    Инициализирует базу данных, создавая необходимые таблицы и индексы
    
    Args:
        db_path: Путь к файлу базы данных
        reset: Если True, удаляет существующую БД и создает новую
    """
    # Если нужно сбросить базу, удаляем файл
    if reset and os.path.exists(db_path):
        try:
            os.remove(db_path)
            logger.info(f"Существующая база данных удалена: {db_path}")
        except Exception as e:
            logger.error(f"Не удалось удалить существующую базу данных: {e}")
            return False
    
    # Подключаемся к базе данных
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Создаем таблицы
        for table_name, create_sql in CREATE_TABLES_SQL.items():
            cursor.execute(create_sql)
            logger.info(f"Таблица {table_name} создана/проверена")
        
        # Создаем индексы
        for index_sql in CREATE_INDEXES_SQL:
            cursor.execute(index_sql)
            logger.info(f"Индекс создан/проверен: {index_sql}")
        
        conn.commit()
        logger.info(f"База данных успешно инициализирована: {db_path}")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def main():
    """Основная функция скрипта"""
    parser = argparse.ArgumentParser(description="ThermoGrid - Инициализация базы данных")
    parser.add_argument("--db", dest="db_path", default="thermogrid.db",
                       help="Путь к файлу базы данных (по умолчанию: thermogrid.db)")
    parser.add_argument("--reset", action="store_true",
                       help="Сбросить существующую базу данных и создать новую")
    
    args = parser.parse_args()
    
    if init_database(args.db_path, args.reset):
        logger.info("Инициализация базы данных завершена успешно")
    else:
        logger.error("Ошибка инициализации базы данных")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())