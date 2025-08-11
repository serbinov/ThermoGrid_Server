# file: test_client.py
import socket
import json
import time
import random

# ИЗМЕНЕНИЕ: Обновленная структура данных для протокола 2.1
test_data = {
  "protocol_version": "2.1",
  "deviceId": "DE:AD:BE:EF:FE:ED",
  "deviceName": "TermoEth Monitor",
  "firmware_version": "v1.55",
  "timestamp_utc": 0,
  "uptime_ms": 3600000,
  "geo": {
    "lat": 55.7558,
    "lon": 37.6173
  },
  "status": {
    "alarm_active": False,
    "alarm_threshold_c": 38.50,
    "network": "ethernet",
    "ip_address": "192.168.0.123"
  },
  "sensors": [
    {
      "id": 0,
      "name": "Server Rack Inlet",
      "data": {
        "temperature_c": 22.75
      }
    },
    {
      "id": 1,
      "name": "Server Rack Outlet",
      "data": {
        "temperature_c": 35.12
      }
    },
    {
      "id": 2,
      "name": "Ambient",
      "data": {
        "temperature_c": 25.50
      }
    }
  ]
}

HOST, PORT = 'localhost', 8080 

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    try:
        s.connect((HOST, PORT))
        print(f"Клиент: Подключился к {HOST}:{PORT}")
        
        # Обновляем динамические данные перед отправкой
        test_data["timestamp_utc"] = int(time.time())
        test_data["uptime_ms"] = random.randint(10000, 500000)
        test_data["sensors"][0]["data"]["temperature_c"] = round(random.uniform(20.0, 25.0), 2)
        test_data["sensors"][1]["data"]["temperature_c"] = round(random.uniform(33.0, 40.0), 2)
        test_data["sensors"][2]["data"]["temperature_c"] = round(random.uniform(22.0, 28.0), 2)
        
        # Отправляем данные с разделителем, как ожидает сервер
        full_message = f"POST /data HTTP/1.1\r\nContent-Type: application/json\r\n\r\n{json.dumps(test_data)}"
        s.sendall(full_message.encode('utf-8'))
        
        print("Клиент: Данные отправлены.")
    except ConnectionRefusedError:
        print(f"Клиент: Не удалось подключиться. Сервер на {HOST}:{PORT} запущен?")
    except Exception as e:
        print(f"Клиент: Произошла ошибка: {e}")