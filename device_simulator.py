#!/usr/bin/env python3
# device_simulator.py - Скрипт симуляции устройств ThermoGrid

import time
import json
import random
import requests
import threading
from datetime import datetime
import socket

# Конфигурация
SERVER_URL = "http://localhost:9090/"  # Измените на свой URL/порт, если требуется
UPDATE_INTERVAL = 10  # Интервал отправки данных (секунды)
DEVICES_COUNT = 15  # Количество устройств для симуляции

# Предопределенные данные для устройств
DEVICE_TYPES = ["ThermoSensor Pro", "TempTrack 3000", "HeatMonitor X2", "ClimateGuard", "ThermoGuard"]
LOCATIONS = ["Серверная", "Офис", "Склад", "Лаборатория", "Производство", 
             "Холодильная камера", "Теплица", "Архив", "Хранилище", "Зона отдыха"]
SENSOR_NAMES = ["Внутренний", "Внешний", "Основной", "Запасной", "Верхний", "Нижний", 
                "Северный", "Южный", "Восточный", "Западный", "Центральный", "Периферийный"]

# Список устройств с их фиксированными параметрами
devices = [
    {
        "id": f"AA:BB:CC:DD:00:{i:02d}",  # MAC как ID
        "deviceName": f"{random.choice(DEVICE_TYPES)} - {random.choice(LOCATIONS)} {i+1}",
        "firmware_version": f"v{random.randint(1,3)}.{random.randint(0,9)}.{random.randint(0,9)}",
        "sensor_count": random.randint(1, 4),  # От 1 до 4 сенсоров
        "alarm_threshold": round(random.uniform(25.0, 35.0), 1),  # Порог тревоги
    } for i in range(DEVICES_COUNT)
]

# Для каждого устройства создаем уникальные имена сенсоров
for device in devices:
    # Выбираем случайные уникальные имена для сенсоров этого устройства
    device_sensor_names = random.sample(SENSOR_NAMES, device["sensor_count"])
    device["sensor_names"] = device_sensor_names

def get_local_ip():
    """Получить локальный IP-адрес машины"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def generate_device_data(device):
    """Генерировать актуальные данные для устройства"""
    # Определим базовую температуру для устройства (для симуляции, чтобы у одного устройства 
    # все сенсоры были примерно в одном диапазоне)
    base_temp = random.uniform(18.0, 28.0)
    
    # Изредка генерируем тревогу
    should_alarm = random.random() < 0.05  # 5% шанс тревоги
    
    # Добавим возмущение к базовой температуре для создания тревоги
    if should_alarm:
        base_temp = device["alarm_threshold"] + random.uniform(0.5, 5.0)
    
    # Создаем данные сенсоров
    sensors = []
    for i in range(device["sensor_count"]):
        # Температура около базовой с небольшим отклонением
        temp = base_temp + random.uniform(-2.0, 2.0)
        # Влажность 30-70%
        humidity = random.uniform(30.0, 70.0)
        
        sensor = {
            "id": i,
            "name": device["sensor_names"][i],
            "type": "dht22",
            "data": {
                "temperature_c": round(temp, 1),
                "humidity": round(humidity, 1)
            }
        }
        sensors.append(sensor)
    
    # Соберем полный JSON пакет
    now = time.time()
    uptime = random.randint(1000, 1000000)  # Случайное время работы в мс
    
    data = {
        "deviceId": device["id"],
        "deviceName": device["deviceName"],
        "firmware_version": device["firmware_version"],
        "uptime_ms": uptime,
        "status": {
            "alarm_active": should_alarm,
            "alarm_threshold_c": device["alarm_threshold"],
            "network": "WiFi",
            "ip_address": get_local_ip()
        },
        "geo": {
            "lat": random.uniform(55.0, 56.0),  # Координаты для примера
            "lon": random.uniform(37.0, 38.0)
        },
        "sensors": sensors
    }
    
    return data

def device_loop(device):
    """Основной цикл работы устройства"""
    print(f"Запущен эмулятор: {device['deviceName']} ({device['id']})")
    
    while True:
        # Генерируем актуальные данные
        data = generate_device_data(device)
        
        try:
            # Отправляем данные на сервер
            response = requests.post(SERVER_URL, json=data)
            
            # Проверяем ответ
            if response.status_code == 200:
                status = "✓" if not data["status"]["alarm_active"] else "🔥 ТРЕВОГА!"
                print(f"{datetime.now().strftime('%H:%M:%S')} | {device['deviceName']} | Отправлено {status}")
            else:
                print(f"Ошибка при отправке данных для {device['deviceName']}: {response.status_code}")
        
        except Exception as e:
            print(f"Ошибка соединения для {device['deviceName']}: {e}")
        
        # Ждем до следующей отправки
        time.sleep(UPDATE_INTERVAL + random.uniform(0, 5))  # Небольшой разброс интервала

def main():
    print(f"=== ThermoGrid Device Simulator ===")
    print(f"Симулируем {DEVICES_COUNT} устройств, отправляя данные на {SERVER_URL}")
    print(f"Интервал обновления: {UPDATE_INTERVAL} секунд (±5с)")
    print("=" * 40)
    
    # Создаем потоки для каждого устройства
    threads = []
    for device in devices:
        t = threading.Thread(target=device_loop, args=(device,))
        t.daemon = True  # Поток завершится, когда завершится основной поток
        threads.append(t)
        t.start()
        # Небольшая задержка между запусками устройств чтобы избежать одновременных запросов
        time.sleep(0.5)
    
    # Ожидаем завершения работы (Ctrl+C)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nПолучен сигнал завершения. Останавливаем симуляцию...")

if __name__ == "__main__":
    main()