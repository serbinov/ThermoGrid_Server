# ThermoGrid Telemetry JSON Protocol — ID: TG‑TJP — Version: v1.0 (tg-tjp/1.0)

This document defines the data exchange format between ThermoGrid devices and the ThermoGrid Server. The protocol uses HTTP + JSON, is easy to implement on microcontrollers, and is resilient to partial field updates.

Audience: firmware developers and integrators. All examples are UTF‑8 encoded. Temperatures are in degrees Celsius.

Canonical name: ThermoGrid Telemetry JSON Protocol (TG‑TJP) v1.0, identifier tg-tjp/1.0.

## Overview

- Transport: HTTP/1.1 or HTTP/2, telemetry is sent via POST.
- URL: server root path `/`.
- Content Type: `application/json`.
- Server response: `200 OK` with JSON `{"status":"ok"}` when accepted.
- Timestamp policy: the server assigns its own receive time to all readings (client timestamps are ignored in v1.0).
- Encoding: UTF‑8, decimal separator is dot (`.`).

## Telemetry Packet (POST /)

The only required field is `deviceId`. All other fields are optional and may be sent partially; the server updates only the provided fields.

Schema:

```json
{
	"deviceId": "string",              // Required. Unique device ID
	"deviceName": "string",            // Optional. Human‑readable name
	"firmware_version": "string",      // Firmware version (e.g., "v3.06")
	"uptime_ms": 12345678,              // Device uptime in milliseconds

	"status": {                         // Device status
		"alarm_active": false,            // Whether the alarm threshold is exceeded
		"alarm_threshold_c": 26.0,        // Alarm threshold in °C
		"network": "WiFi|Ethernet|N/A", // Network type (free text)
		"ip_address": "192.168.1.49"    // Current device IP
	},

	"geo": {                            // Optional geolocation
		"lat": 55.707059,
		"lon": 37.608188
	},

	"sensors": [                        // Up to 4 sensors (0..3), order irrelevant
		{
			"id": 0,                        // Required within sensor
			"name": "Sensor 1",           // Optional sensor name
			"type": "ds18b20",            // Free‑form sensor type
			"data": {
				"temperature_c": 13.9,       // Temperature, °C
				"humidity": null             // Relative humidity, % (if present; else null or omit)
			}
		}
		// ... up to 3 more sensors
	]
}
```

Server behavior (v1.0):

- `deviceId` is the primary key. First arrival creates a device record; subsequent packets update it.
- Latest measurements per sensor are stored in the `sensors` table (temperature, humidity, last_reading_time).
- History is appended to the `readings` table for each sensor when `data.temperature_c` is present.
- Reading timestamps are server receive times in UNIX seconds; client timestamps are ignored in v1.0.

### Minimal packet example

```json
{
	"deviceId": "SIM:20:78:29:0001",
	"sensors": [
		{ "id": 0, "data": { "temperature_c": 21.8 } }
	]
}
```

### Full packet example (4 sensors)

```json
{
	"deviceId": "SIM:20:78:29:0001",
	"deviceName": "ThermoGrid #1",
	"firmware_version": "v3.06",
	"uptime_ms": 8451000,
	"status": {
		"alarm_active": false,
		"alarm_threshold_c": 26.0,
		"network": "WiFi",
		"ip_address": "192.168.1.49"
	},
	"geo": { "lat": 55.707059, "lon": 37.608188 },
	"sensors": [
		{ "id": 0, "name": "Sensor 1", "type": "ds18b20", "data": { "temperature_c": 13.9 } },
		{ "id": 1, "name": "Sensor 2", "type": "ds18b20", "data": { "temperature_c": 12.1 } },
		{ "id": 2, "name": "Sensor 3", "type": "ds18b20", "data": { "temperature_c": 13.0 } },
		{ "id": 3, "name": "Sensor 4", "type": "ds18b20", "data": { "temperature_c": 11.9 } }
	]
}
```

### Server response

```json
{"status":"ok"}
```

On validation or internal errors, the server returns 4xx/5xx with a short JSON message:

```json
{"detail":"validation error: deviceId is required"}
```

## Server REST API (used by UI/integrations)

These endpoints are used by the web UI and may be handy for external scripts.

### GET /api/devices

List of devices (summary):

```json
[
	{
		"id": "SIM:20:78:29:0001",
		"deviceName": "ThermoGrid #1",
		"ip_address": "192.168.1.49",
		"alarm_active": false,
		"last_seen": 1723229400
	}
]
```

### GET /api/device/{device_id}

Device details. Returns all columns from `devices` plus `sensors` with latest readings:

```json
{
	"id": "SIM:20:78:29:0001",
	"deviceName": "ThermoGrid #1",
	"last_seen": 1723229400,
	"firmware_version": "v3.06",
	"uptime_ms": 8451000,
	"alarm_active": false,
	"alarm_threshold_c": 26.0,
	"network": "WiFi",
	"ip_address": "192.168.1.49",
	"lat": 55.707059,
	"lon": 37.608188,
	"raw_json": "{...last device packet...}",
	"sensors": [
		{ "sensor_id": 0, "name": "Sensor 1", "type": "ds18b20", "latest_temperature": 13.9, "latest_humidity": null, "last_reading_time": 1723229400 },
		{ "sensor_id": 1, "name": "Sensor 2", "type": "ds18b20", "latest_temperature": 12.1, "latest_humidity": null, "last_reading_time": 1723229400 }
	]
}
```

### POST /api/history

History request for a single sensor.

Payload (JSON):

```json
{
	"device_id": "SIM:20:78:29:0001",   // Required
	"sensor_id": 0,                      // Required (0..3)
	"start_time": 1723225800,            // Optional (UNIX seconds)
	"end_time": 1723229400,              // Optional (UNIX seconds)
	"max_points": 1000                   // Optional. Server may downsample
}
```

Response (ascending by time):

```json
[
	{ "timestamp": 1723225800, "temperature_c": 21.8 },
	{ "timestamp": 1723225860, "temperature_c": 21.9 }
]
```

Notes:

- If `start_time`/`end_time` are omitted, latest N rows are returned (then reversed to ascending).
- Currently only `temperature_c` is returned; humidity is stored but not emitted by history.

### GET /api/device_range/{device_id}

Global time range (min/max) across all sensors for the device — used by the UI mini‑timeline.

```json
{ "min": 1719950000, "max": 1723229400 }
```

### GET /api/settings

```json
{
	"server_port": "9090",
	"ntp_enabled": false,
	"max_points": 1000,
	"app_version": "0.1.0",
	"developer": "Serbinov Oleg"
}
```

### POST /api/settings

```json
{
	"server_port": "9090",    // Requires app restart to take effect
	"ntp_enabled": true,       // Built‑in NTP server (UDP 123)
	"max_points": 1000
}
```

## Firmware recommendations

- Send telemetry up to once per second per sensor under normal operation; during events (alarm, first start) higher rates are acceptable.
- Sensor identifier (`id`) is an integer 0..3. Stable names `Sensor 1..4` are convenient for the UI.
- If a sensor is temporarily missing, omit it from `sensors` or send `data: { "temperature_c": null }` (such points are not saved to history).
- Use retries with exponential backoff on network errors; the protocol is idempotent at the “latest record” level.
- Ensure numeric correctness (avoid `NaN/Infinity`).

## Versioning

v1.0 (tg‑tjp/1.0):
- Base structure of device/status/geo/sensors.
- Server‑side timestamps for history.
- REST API for devices, history, and settings.

— End of English version —

---

# Русская версия / Russian version

Этот документ описывает формат обмена данными между устройствами ThermoGrid и сервером ThermoGrid Server. Протокол основан на HTTP + JSON, прост в реализации на микроконтроллерах и устойчив к частичным обновлениям полей.

Документ ориентирован на разработчиков прошивок и интеграторов. Все примеры — в кодировке UTF‑8. Числовые значения температур — в градусах Цельсия.

— Каноническое имя протокола: ThermoGrid Telemetry JSON Protocol (TG‑TJP) v1.0, идентификатор tg-tjp/1.0.

## Общее

- Транспорт: HTTP 1.1 или 2.0, метод POST для телеметрии.
- Адрес: корневой путь сервера `/`.
- Тип содержимого: `Content-Type: application/json`.
- Ответ сервера: `200 OK` и JSON `{"status":"ok"}` при успешном приёме.
- Отметка времени: сервер фиксирует время получения пакета и присваивает его всем показаниям (клиентский timestamp игнорируется в v1.0).
- Кодировка: UTF‑8, десятичная точка — точка (`.`).

## Пакет телеметрии (POST /)

Минимально необходимое поле — `deviceId`. Остальные поля желательны, но допускаются по частям: сервер обновляет только те сведения, которые пришли.

Структура:

```json
{
	"deviceId": "string",              // Обязательное. Уникальный ID устройства
	"deviceName": "string",            // Необязательное. Человекочитаемое имя
	"firmware_version": "string",      // Версия прошивки (например, "v3.06")
	"uptime_ms": 12345678,              // Аптайм устройства в миллисекундах

	"status": {                         // Объект статуса
		"alarm_active": false,            // Превышен ли порог тревоги
		"alarm_threshold_c": 26.0,        // Порог тревоги, °C
		"network": "WiFi|Ethernet|N/A", // Тип сети (произвольная строка)
		"ip_address": "192.168.1.49"    // Текущий IP адрес устройства
	},

	"geo": {                            // Геопозиция (опционально)
		"lat": 55.707059,
		"lon": 37.608188
	},

	"sensors": [                        // До 4-х датчиков (0..3), порядок не важен
		{
			"id": 0,                        // Обязательное в рамках датчика
			"name": "Sensor 1",           // Необязательное имя датчика
			"type": "ds18b20",            // Произвольное обозначение типа
			"data": {
				"temperature_c": 13.9,       // Температура, °C
				"humidity": null             // Влажность, % (если есть; иначе null/поле можно опустить)
				// Дополнительные поля допустимы, но сервер v1.0 их игнорирует
			}
		}
		// ... до 3 дополнительных датчиков
	]
}
```

Замечания по поведению сервера v1.0:

- Поле `deviceId` используется как первичный ключ. При первом приходе устройства создаётся запись, далее обновляется.
- Столбцы последнего измерения по датчику хранятся в таблице `sensors` (температура, влажность, время последнего чтения).
- История фиксируется в таблице `readings` для каждого сенсора, когда в пакете присутствует `data.temperature_c`.
- Временная метка истории — время получения серверами (UNIX seconds). Клиентские timestamps в v1.0 не анализируются.

### Пример минимального пакета

```json
{
	"deviceId": "SIM:20:78:29:0001",
	"sensors": [
		{ "id": 0, "data": { "temperature_c": 21.8 } }
	]
}
```

### Пример полного пакета с 4 датчиками

```json
{
	"deviceId": "SIM:20:78:29:0001",
	"deviceName": "ThermoGrid #1",
	"firmware_version": "v3.06",
	"uptime_ms": 8451000,
	"status": {
		"alarm_active": false,
		"alarm_threshold_c": 26.0,
		"network": "WiFi",
		"ip_address": "192.168.1.49"
	},
	"geo": { "lat": 55.707059, "lon": 37.608188 },
	"sensors": [
		{ "id": 0, "name": "Sensor 1", "type": "ds18b20", "data": { "temperature_c": 13.9 } },
		{ "id": 1, "name": "Sensor 2", "type": "ds18b20", "data": { "temperature_c": 12.1 } },
		{ "id": 2, "name": "Sensor 3", "type": "ds18b20", "data": { "temperature_c": 13.0 } },
		{ "id": 3, "name": "Sensor 4", "type": "ds18b20", "data": { "temperature_c": 11.9 } }
	]
}
```

### Ответ сервера

```json
{"status":"ok"}
```

При ошибках валидации или внутренних сбоях сервер вернёт код 4xx/5xx с кратким описанием в JSON:

```json
{"detail":"validation error: deviceId is required"}
```

## REST API сервера (для UI/интеграций)

Ниже перечислены доступные эндпоинты, которые использует веб‑интерфейс ThermoGrid. Они могут быть полезны для внешних интеграций/скриптов.

### GET /api/devices

Список устройств (краткая информация):

```json
[
	{
		"id": "SIM:20:78:29:0001",
		"deviceName": "ThermoGrid #1",
		"ip_address": "192.168.1.49",
		"alarm_active": false,
		"last_seen": 1723229400
	}
]
```

### GET /api/device/{device_id}

Подробности по устройству. Сервер возвращает все колонки таблицы `devices`, а также массив `sensors` с последними показаниями:

```json
{
	"id": "SIM:20:78:29:0001",
	"deviceName": "ThermoGrid #1",
	"last_seen": 1723229400,
	"firmware_version": "v3.06",
	"uptime_ms": 8451000,
	"alarm_active": false,
	"alarm_threshold_c": 26.0,
	"network": "WiFi",
	"ip_address": "192.168.1.49",
	"lat": 55.707059,
	"lon": 37.608188,
	"raw_json": "{...последний пакет от устройства...}",
	"sensors": [
		{ "sensor_id": 0, "name": "Sensor 1", "type": "ds18b20", "latest_temperature": 13.9, "latest_humidity": null, "last_reading_time": 1723229400 },
		{ "sensor_id": 1, "name": "Sensor 2", "type": "ds18b20", "latest_temperature": 12.1, "latest_humidity": null, "last_reading_time": 1723229400 }
	]
}
```

### POST /api/history

Запрос истории по одному датчику.

Параметры запроса (JSON):

```json
{
	"device_id": "SIM:20:78:29:0001",   // Обязательное
	"sensor_id": 0,                      // Обязательное (0..3)
	"start_time": 1723225800,            // Опционально (UNIX seconds)
	"end_time": 1723229400,              // Опционально (UNIX seconds)
	"max_points": 1000                   // Опционально. Сервер может прореживать данные
}
```

Ответ (упорядочено по времени ASC):

```json
[
	{ "timestamp": 1723225800, "temperature_c": 21.8 },
	{ "timestamp": 1723225860, "temperature_c": 21.9 }
]
```

Примечания:

- Если `start_time`/`end_time` не заданы, возвращаются последние N записей (после разворота в возрастающий порядок).
- В текущей версии история возвращает только `temperature_c`. Поле влажности сохраняется, но из history не выдаётся.

### GET /api/device_range/{device_id}

Глобальный диапазон времени (мин/макс) по всем сенсорам устройства — используется мини‑шкалой в UI.

```json
{ "min": 1719950000, "max": 1723229400 }
```

### GET /api/settings

```json
{
	"server_port": "9090",
	"ntp_enabled": false,
	"max_points": 1000,
	"app_version": "0.1.0",
	"developer": "Serbinov Oleg"
}
```

### POST /api/settings

```json
{
	"server_port": "9090",    // Требует перезапуска приложения для применения
	"ntp_enabled": true,       // Встроенный NTP‑сервер (UDP 123)
	"max_points": 1000
}
```

## Рекомендации для прошивки

- Отправляйте телеметрию не чаще 1 раза в секунду на датчик при нормальном режиме; при событиях (тревога, первый старт) можно чаще.
- Идентификатор датчика (`id`) — целое число 0..3. Для взаимодействия с UI удобно сохранять стабильные имена `Sensor 1..4`.
- Если датчик временно отсутствует — можно не включать его в массив `sensors` либо передавать `data: { "temperature_c": null }` (в истории такая точка не будет записана).
- При сетевых сбоях используйте повтор с экспоненциальной задержкой; протокол идемпотентен на уровне "последняя запись".
- Пожалуйста, следите за корректностью чисел (не отправляйте `NaN/Infinity`).

## Изменения версий

v1.0 (tg‑tjp/1.0):
- Базовая структура устройства, статуса, гео и массива датчиков.
- Сервер выставляет серверный timestamp в истории.
- REST API для устройств, истории и настроек.

— Конец документа.
