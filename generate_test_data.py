#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Generate test data for ThermoGrid Server AI features
"""

import sqlite3
import time
import json
import random
import math

def generate_test_data(db_path="thermogrid.db", days_back=7):
    """Generate realistic temperature test data"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Test device data
        device_id = "TEST:AI:DEMO:0001"
        device_name = "AI Demo Device"
        
        current_time = int(time.time())
        start_time = current_time - (days_back * 24 * 60 * 60)
        
        # Create device record
        cursor.execute("""
            INSERT OR REPLACE INTO devices 
            (id, deviceName, firmware_version, network, ip_address, last_seen, uptime_ms, 
             alarm_active, alarm_threshold_c, lat, lon, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device_id, device_name, "1.0.0", "wifi", "192.168.1.100", 
            current_time, 86400000, 0, 25.0, 55.7558, 37.6176,
            json.dumps({"test": "data"})
        ))
        
        # Create sensor records
        for sensor_id in range(4):
            sensor_name = f"AI Test Sensor {sensor_id + 1}"
            cursor.execute("""
                INSERT OR REPLACE INTO sensors 
                (device_id, sensor_id, name, type, temperature, humidity, last_reading_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                device_id, sensor_id, sensor_name, "ds18b20", 
                20.0 + random.uniform(-2, 2), 
                50.0 + random.uniform(-10, 10), 
                current_time
            ))
        
        # Generate historical readings
        print(f"Генерация данных за {days_back} дней для устройства {device_id}...")
        
        # Base temperature follows daily cycle
        for hour_offset in range(0, days_back * 24, 1):  # Every hour
            timestamp = start_time + (hour_offset * 60 * 60)
            
            # Daily temperature cycle (cooler at night, warmer during day)
            hour_of_day = (timestamp // 3600) % 24
            daily_temp_base = 20.0 + 5.0 * math.sin((hour_of_day - 6) * math.pi / 12)
            
            for sensor_id in range(4):
                # Each sensor has slight variations
                sensor_offset = sensor_id * 0.5
                seasonal_drift = random.uniform(-0.1, 0.1)  # Small random drift
                
                # Add some noise
                noise = random.uniform(-1.0, 1.0)
                
                # Occasional anomalies (5% chance)
                if random.random() < 0.05:
                    anomaly = random.uniform(-8, 8)  # Larger anomaly
                else:
                    anomaly = 0
                
                final_temp = daily_temp_base + sensor_offset + seasonal_drift + noise + anomaly
                humidity = 50.0 + random.uniform(-15, 15)
                
                cursor.execute("""
                    INSERT INTO readings (device_id, sensor_id, timestamp, temperature_c, humidity)
                    VALUES (?, ?, ?, ?, ?)
                """, (device_id, sensor_id, timestamp, round(final_temp, 1), round(humidity, 1)))
        
        conn.commit()
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM readings WHERE device_id = ?", (device_id,))
        count = cursor.fetchone()[0]
        
        print(f"✅ Создано {count} записей температурных данных")
        print(f"📊 Устройство: {device_name} (ID: {device_id})")
        print(f"🌡️ Данные за последние {days_back} дней с почасовыми измерениями")
        print(f"🔬 4 сенсора с реалистичными суточными циклами и случайными аномалиями")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при генерации тестовых данных: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("🚀 Генерация тестовых данных для AI функций ThermoGrid...")
    if generate_test_data():
        print("✨ Тестовые данные успешно созданы!")
        print("\n📋 Теперь вы можете:")
        print("1. Запустить сервер: python server_headless.py")
        print("2. Открыть настройки и оплатить подписку на ИИ")
        print("3. Протестировать предсказание температуры и обнаружение аномалий")
    else:
        print("💥 Не удалось создать тестовые данные")