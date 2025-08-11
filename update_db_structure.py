#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Скрипт для обновления структуры существующей базы данных ThermoGrid
"""

import sqlite3
import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_NAME = "thermogrid.db"

def update_database_structure():
    """
    Обновляет структуру базы данных, добавляя недостающие колонки
    """
    conn = None
    try:
        # Проверяем существование файла базы данных
        if not os.path.exists(DB_NAME):
            logger.error(f"База данных {DB_NAME} не найдена")
            return False
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Получаем информацию о существующих колонках в таблице sensors
        cursor.execute("PRAGMA table_info(sensors)")
        columns = [column[1] for column in cursor.fetchall()]
        logger.info(f"Текущие колонки в таблице sensors: {columns}")
        
        # Список колонок для добавления и их типы
        columns_to_add = {
            "temperature": "REAL",
            "humidity": "REAL",
            "last_reading_time": "INTEGER"
        }
        
        # Добавляем недостающие колонки
        for column_name, column_type in columns_to_add.items():
            if column_name not in columns:
                sql = f"ALTER TABLE sensors ADD COLUMN {column_name} {column_type}"
                logger.info(f"Выполняем: {sql}")
                cursor.execute(sql)
                logger.info(f"Добавлена колонка {column_name} с типом {column_type}")
            else:
                logger.info(f"Колонка {column_name} уже существует")
        
        # Обновляем данные в колонках temperature и humidity из таблицы readings
        if "temperature" in columns_to_add and "temperature" not in columns:
            logger.info("Обновляем значения в колонках temperature и humidity из таблицы readings...")
            
            # Получаем последние показания из таблицы readings для каждого сенсора
            cursor.execute("""
                WITH latest_readings AS (
                    SELECT 
                        device_id,
                        sensor_id,
                        temperature_c,
                        humidity,
                        timestamp,
                        ROW_NUMBER() OVER (PARTITION BY device_id, sensor_id ORDER BY timestamp DESC) as rn
                    FROM readings
                )
                SELECT device_id, sensor_id, temperature_c, humidity, timestamp
                FROM latest_readings
                WHERE rn = 1
            """)
            
            latest_readings = cursor.fetchall()
            logger.info(f"Получено {len(latest_readings)} записей для обновления")
            
            # Обновляем данные в таблице sensors
            for reading in latest_readings:
                device_id, sensor_id, temperature, humidity, timestamp = reading
                cursor.execute("""
                    UPDATE sensors
                    SET temperature = ?, humidity = ?, last_reading_time = ?
                    WHERE device_id = ? AND sensor_id = ?
                """, (temperature, humidity, timestamp, device_id, sensor_id))
                
                if cursor.rowcount > 0:
                    logger.info(f"Обновлен датчик {device_id}:{sensor_id} с температурой {temperature} и временем {timestamp}")
        
        conn.commit()
        logger.info("Обновление структуры базы данных успешно завершено")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка при обновлении структуры базы данных: {e}")
        if conn:
            conn.rollback()
        return False
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if update_database_structure():
        logger.info("Скрипт обновления структуры базы данных успешно выполнен")
        sys.exit(0)
    else:
        logger.error("Не удалось обновить структуру базы данных")
        sys.exit(1)