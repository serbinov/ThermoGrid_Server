#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ThermoGrid - Генератор исторических данных
==========================================
Скрипт генерирует исторические данные для устройств за указанный период
и заполняет ими базу данных или отправляет на сервер.
"""

import os
import sys
import json
import time
import random
import sqlite3
import requests
import argparse
import math
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы и настройки
DEFAULT_SERVER_URL = "http://localhost:9090"
DEFAULT_DB_PATH = "thermogrid.db"
DEFAULT_DEVICE_COUNT = 10
DEFAULT_DAYS = 10
DEFAULT_READINGS_PER_HOUR = 6  # Каждые 10 минут
DEFAULT_SENSORS_PER_DEVICE = 4


def generate_device_id(index):
    """Генерирует ID устройства в формате 'SIM:XX:YY:ZZ:INDEX'"""
    return f"SIM:{random.randint(10, 99)}:{random.randint(10, 99)}:{random.randint(10, 99)}:{index:04d}"


def generate_device_name(index):
    """Генерирует имя устройства"""
    locations = ["Kitchen", "Living Room", "Bedroom", "Office", "Bathroom", 
                "Garage", "Basement", "Attic", "Garden", "Balcony"]
    return f"Device {index} ({locations[index % len(locations)]})"


def generate_device_data(device_id, device_name, timestamp, seed=None, sensors_count=DEFAULT_SENSORS_PER_DEVICE):
    """Генерирует данные устройства для указанного времени"""
    if seed is not None:
        random.seed(seed)
    
    # Основные данные устройства
    base_temp = 20 + random.uniform(-2, 2)  # Базовая температура
    day_variation = 3  # Дневная вариация температуры
    
    # Вычисляем время дня (0-1), где 0 - полночь, 0.5 - полдень
    hour = datetime.fromtimestamp(timestamp).hour
    time_of_day = hour / 24.0
    
    # Дневная вариация: теплее днем, прохладнее ночью
    time_factor = math.sin(time_of_day * 2 * math.pi)
    daily_temp_adjust = time_factor * day_variation
    
    # Случайные отклонения для каждого устройства
    device_temp_offset = random.uniform(-5, 5)
    
    # Генерируем данные о сенсорах
    sensors = []
    for sensor_id in range(sensors_count):
        # Создаем уникальные значения для каждого сенсора
        sensor_temp_offset = random.uniform(-1.5, 1.5)
        base_temp_with_offsets = base_temp + device_temp_offset + sensor_temp_offset + daily_temp_adjust
        
        # Генерируем влажность (40-60%)
        humidity = 50 + random.uniform(-10, 10)
        
        sensors.append({
            "id": sensor_id,
            "name": f"Sensor {sensor_id + 1}",
            "type": "DHT22",
            "data": {
                "temperature_c": round(base_temp_with_offsets, 1),
                "humidity": round(humidity, 1)
            }
        })
    
    # Определяем, есть ли тревога (температура выше 26°C на любом сенсоре)
    alarm_threshold = 26.0
    alarm_active = any(sensor["data"]["temperature_c"] > alarm_threshold for sensor in sensors)
    
    # Формируем полные данные устройства
    return {
        "deviceId": device_id,
        "deviceName": device_name,
        "timestamp": timestamp,
        "firmware_version": "v3.5.7",
        "uptime_ms": random.randint(3600000, 86400000 * 30),  # От часа до 30 дней
        "status": {
            "alarm_active": alarm_active,
            "alarm_threshold_c": alarm_threshold,
            "network": "WiFi",
            "ip_address": f"192.168.1.{random.randint(2, 254)}"
        },
        "geo": {
            "lat": 55.7558 + random.uniform(-0.05, 0.05),
            "lon": 37.6173 + random.uniform(-0.05, 0.05)
        },
        "sensors": sensors
    }


def insert_into_database(db_path, data):
    """Вставляет данные напрямую в базу данных"""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем наличие таблицы devices, если нет - создаем структуру БД
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='devices'")
        if not cursor.fetchone():
            cursor.execute('''
            CREATE TABLE devices (
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
            ''')
            cursor.execute('''
            CREATE TABLE sensors (
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
            ''')
            cursor.execute('''
            CREATE TABLE readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT,
                sensor_id INTEGER,
                timestamp INTEGER,
                temperature_c REAL,
                humidity REAL
            )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_readings_device ON readings (device_id, sensor_id, timestamp)')
        
        device_id = data["deviceId"]
        timestamp = data["timestamp"]
        
        # Вставляем или обновляем данные устройства
        cursor.execute(
            """
            INSERT OR REPLACE INTO devices (
                id, deviceName, firmware_version, network, ip_address, last_seen, 
                uptime_ms, alarm_active, alarm_threshold_c, lat, lon, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                device_id,
                data["deviceName"],
                data["firmware_version"],
                data["status"]["network"],
                data["status"]["ip_address"],
                timestamp,
                data["uptime_ms"],
                1 if data["status"]["alarm_active"] else 0,
                data["status"]["alarm_threshold_c"],
                data["geo"]["lat"],
                data["geo"]["lon"],
                json.dumps(data)
            )
        )
        
        # Обрабатываем данные сенсоров
        for sensor in data["sensors"]:
            sensor_id = sensor["id"]
            temp = sensor["data"].get("temperature_c")
            humidity = sensor["data"].get("humidity")
            
            # Получаем имена столбцов таблицы sensors
            cursor.execute("PRAGMA table_info(sensors)")
            columns = {column[1]: column[0] for column in cursor.fetchall()}
            
            # Проверяем, какие имена колонок используются для температуры и влажности
            temp_column = "latest_temperature"
            humidity_column = "latest_humidity"
            
            # Создаем динамический запрос на основе существующих колонок
            if "latest_temperature" not in columns:
                if "temperature" in columns:
                    temp_column = "temperature"
                    
            if "latest_humidity" not in columns:
                if "humidity" in columns:
                    humidity_column = "humidity"
            
            # Вставляем или обновляем данные сенсора с правильными именами колонок
            cursor.execute(
                f"""
                INSERT OR REPLACE INTO sensors (
                    device_id, sensor_id, name, type, {temp_column}, {humidity_column}, last_reading_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    sensor_id,
                    sensor["name"],
                    sensor["type"],
                    temp,
                    humidity,
                    timestamp
                )
            )
            
            # Добавляем запись показаний
            cursor.execute(
                """
                INSERT INTO readings (device_id, sensor_id, timestamp, temperature_c, humidity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    device_id,
                    sensor_id,
                    timestamp,
                    temp,
                    humidity
                )
            )
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка при записи в БД: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def send_to_server(url, data):
    """Отправляет данные на сервер"""
    try:
        response = requests.post(url, json=data, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ошибка при отправке данных на сервер: {e}")
        return False


def generate_history(args):
    """Генерирует историю данных и вставляет в базу данных"""
    device_count = args.devices
    days_of_history = args.days
    readings_per_hour = args.readings_per_hour
    sensors_per_device = args.sensors
    
    # Создаем список устройств
    devices = []
    for i in range(1, device_count + 1):
        device_id = generate_device_id(i)
        device_name = generate_device_name(i)
        devices.append((device_id, device_name))
    
    # Устанавливаем временной диапазон
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days_of_history)
    
    # Вычисляем количество записей на устройство
    hours = days_of_history * 24
    total_readings = hours * readings_per_hour
    
    logger.info(f"Генерация {total_readings} записей для каждого из {device_count} устройств...")
    logger.info(f"Период: с {start_time} по {end_time}")
    logger.info(f"Всего будет создано {total_readings * device_count * sensors_per_device} записей показаний")
    
    # Инициализация счетчика для отображения прогресса
    total_records = total_readings * device_count
    progress_step = max(1, total_records // 50)  # Показывать прогресс каждые ~2%
    
    records_processed = 0
    start_processing_time = time.time()
    
    # Для каждого устройства генерируем историю
    for device_idx, (device_id, device_name) in enumerate(devices):
        # Фиксируем seed для устройства, чтобы данные имели некоторую последовательность
        device_seed = hash(device_id) % 10000
        
        # Генерируем временные точки через равные интервалы
        for hour in range(hours):
            for reading in range(readings_per_hour):
                # Вычисляем временную метку для текущего показания
                minutes_offset = (60 // readings_per_hour) * reading
                current_time = start_time + timedelta(hours=hour, minutes=minutes_offset)
                timestamp = int(current_time.timestamp())
                
                # Создаем данные устройства для этого момента времени
                reading_seed = device_seed + hour + (reading / readings_per_hour)
                data = generate_device_data(
                    device_id, 
                    device_name, 
                    timestamp, 
                    seed=reading_seed, 
                    sensors_count=sensors_per_device
                )
                
                # Вставляем данные в базу или отправляем на сервер
                if args.direct_db:
                    success = insert_into_database(args.db_path, data)
                else:
                    success = send_to_server(args.server_url, data)
                
                if not success:
                    logger.warning(f"Не удалось сохранить данные для устройства {device_id} на метке времени {current_time}")
                
                # Обновляем счетчик и показываем прогресс
                records_processed += 1
                if records_processed % progress_step == 0:
                    elapsed = time.time() - start_processing_time
                    percent = (records_processed / total_records) * 100
                    logger.info(f"Прогресс: {percent:.1f}% ({records_processed}/{total_records}), " 
                               f"прошло {elapsed:.1f} сек")
    
    # Завершение
    total_time = time.time() - start_processing_time
    logger.info(f"Генерация данных завершена за {total_time:.1f} сек.")
    logger.info(f"Создано {records_processed} записей.")


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="ThermoGrid - Генератор исторических данных")
    parser.add_argument("--server", dest="server_url", default=DEFAULT_SERVER_URL,
                        help=f"URL сервера (по умолчанию: {DEFAULT_SERVER_URL})")
    parser.add_argument("--db", dest="db_path", default=DEFAULT_DB_PATH,
                        help=f"Путь к БД (по умолчанию: {DEFAULT_DB_PATH})")
    parser.add_argument("--direct-db", action="store_true", 
                        help="Записывать данные напрямую в БД, минуя сервер")
    parser.add_argument("--devices", type=int, default=DEFAULT_DEVICE_COUNT,
                        help=f"Количество устройств (по умолчанию: {DEFAULT_DEVICE_COUNT})")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"Количество дней истории (по умолчанию: {DEFAULT_DAYS})")
    parser.add_argument("--readings-per-hour", type=int, default=DEFAULT_READINGS_PER_HOUR,
                        help=f"Количество показаний в час (по умолчанию: {DEFAULT_READINGS_PER_HOUR})")
    parser.add_argument("--sensors", type=int, default=DEFAULT_SENSORS_PER_DEVICE,
                        help=f"Количество сенсоров на устройство (по умолчанию: {DEFAULT_SENSORS_PER_DEVICE})")
    
    args = parser.parse_args()
    
    try:
        # Запускаем генерацию данных
        generate_history(args)
        return 0
    except KeyboardInterrupt:
        logger.info("Прерывание пользователем, завершение работы...")
        return 1
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())