# ThermoGrid Server — Overview / Обзор

English (EN) below, Русский (RU) ниже.

---

## EN — What is ThermoGrid Server?
ThermoGrid Server is a lightweight web application for collecting, storing, and visualizing temperature (and humidity) readings from networked devices. It provides a browser-based dashboard with real-time and historical charts, device information, and performance controls suitable for embedded or desktop environments.

Built for simplicity and speed:
- Backend: FastAPI + SQLite (single-file DB) + Uvicorn
- Frontend: HTML/CSS/JS, Chart.js with date-fns time adapter
- Desktop tray + optional NTP: PySide6 (system tray icon; optional NTP server)

Use cases:
- Monitor temperature sensors across multiple devices
- Inspect per-sensor historical data with interactive timeline
- Export/extend via simple HTTP API

### Key Features
- Device list with quick filter and status coloring
- Sensor cards (up to 4) with latest temperature and measurement time
- Interactive chart:
  - Canvas crosshair with red dashed line and triangle handle
  - Click/drag to move along time; cards reflect values at cursor time
  - Period presets (1/3/6/12/24 hours, 7 days, All time)
  - Daily start markers: thin grey dashed day-boundary lines
  - Navigation buttons: back, now, forward
  - “All time” disables back/forward and spans entire history
  - Loading indicator when fetching from DB
  - Time info strip with compact range and mini timeline
- Performance controls:
  - Max points per chart (default: 1000) with backend downsampling
  - Approximation toggle (simple 3-point moving average smoothing)
- Settings page: server port, NTP switch, max points, links for repo/protocol
- Optional built-in NTP server (UDP 123)
- JSON data inspection view

### Technology Stack
- Python: FastAPI, Uvicorn, sqlite3, PySide6, socketserver (NTP)
- Frontend: Chart.js, chartjs-adapter-date-fns, vanilla JS, CSS
- Database: SQLite file `thermogrid.db`
- Packaging assets: `icons/`, static files under `static/`

### Project Structure (selected)
- `main.py` — app entrypoint (FastAPI, tray, NTP, DB, routes)
- `index.html` — main UI
- `static/app.js`, `static/style.css` — front-end logic/styles
- `thermogrid.db` — SQLite database (created/used at runtime)
- `init_db.py`, `update_db_structure.py` — DB helpers
- `device_simulator.py` — sample simulator (optional)
- `backups/` — archives and DB backups
- `reference/` — reference/legacy UI code (PyQt)

### Data Model (DB Tables)
- `devices(id, deviceName, last_seen, firmware_version, uptime_ms, alarm_active, alarm_threshold_c, network, ip_address, lat, lon, raw_json)`
- `sensors(device_id, sensor_id, name, type, temperature, humidity, last_reading_time)`
- `readings(device_id, sensor_id, timestamp, temperature_c, humidity)`
- `settings(key, value)`

### API
- GET `/api/devices` → list devices
- GET `/api/device/{id}` → device details with sensors and latest readings
- POST `/api/history` → historical points for sensor
  - Request JSON: `{ device_id, sensor_id, start_time?, end_time?, max_points? }`
  - Response JSON: `[ { timestamp, temperature_c }, ... ]`
  - Downsampling: backend evenly reduces point count to `max_points` (or settings default 1000)
- GET `/api/settings` → server_ip, server_port, ntp_enabled, max_points, app_version, repo_url, json_protocol_url, developer
- POST `/api/settings` → update: `server_port`, `ntp_enabled`, `max_points`, `repo_url`, `json_protocol_url`

### Frontend Behavior Highlights
- Crosshair is drawn on canvas (no DOM slider UI), red dashed vertical line with a bottom triangle. Line width is thin; day boundaries rendered in grey dashed lines across plot.
- Clicking or dragging on the chart moves the crosshair; the sensor cards update to the nearest readings for that time.
- When not at the latest time, cards get a visual highlight; after 5s inactivity, the chart returns to the latest data point.
- Period buttons rebuild the chart; non-"All time" periods are anchored to the latest available reading.

### Settings and Performance
- Max points per chart: default 1000; applies server-side downsampling for every history request.
- Approximation (smoothing): 3-point moving average applied client-side to reduce noise without changing storage.
- NTP server: optional; controlled from settings (requires UDP 123 binding; might need admin permissions).

### Running the App (Windows, PowerShell)
Prerequisites:
- Python 3.10+ (recommended 3.11/3.12)
- Packages: fastapi, uvicorn, PySide6

Steps:
1) Install dependencies (optional; adapt to your environment):
```
py -m pip install fastapi uvicorn PySide6
```
2) Start the server:
```
py main.py
```
3) Your default browser should open automatically; if not, visit the shown address (by default http://127.0.0.1:9090). The “Settings” page shows the real server IP of this machine.

### Configuration
- All settings persisted in SQLite table `settings`.
- Server port change requires app restart.
- Max points: minimum 100; default 1000; applies to each sensor series request.
- Links: you can store repo URL and JSON protocol URL; shown in the “About” dialog.

### About Dialog
- Shows: app version, server IP, repository link, JSON protocol link, developer (Serbinov Oleg), and tips.

---

## RU — Что такое ThermoGrid Server?
ThermoGrid Server — лёгкое веб‑приложение для сбора, хранения и визуализации показаний температуры (и влажности) от сетевых устройств. Предоставляет панель в браузере с графиками в реальном времени и историей, информацией об устройствах и контролями производительности. Подходит для встраиваемых и настольных сценариев.

Основа:
- Бэкенд: FastAPI + SQLite (файл БД) + Uvicorn
- Фронтенд: HTML/CSS/JS, Chart.js с адаптером времени date-fns
- Системный трей + опциональный NTP: PySide6 (значок в трее; NTP‑сервер при необходимости)

Сценарии использования:
- Мониторинг датчиков температуры на нескольких устройствах
- Просмотр истории по каждому датчику с интерактивной временной шкалой
- Интеграция через простой HTTP API

### Основные возможности
- Список устройств с быстрым фильтром и цветовым статусом
- Карточки датчиков (до 4) с последней температурой и временем измерения
- Интерактивный график:
  - Красная пунктирная вертикальная линия с треугольником, рисуется на канвасе
  - Клик/перетаскивание по времени; карточки показывают значения на выбранный момент
  - Пресеты периода (1/3/6/12/24 часа, 7 суток, Всё время)
  - Тонкие серые пунктиры в начале суток (локальное время)
  - Кнопки навигации: назад, сейчас, вперёд
  - “Всё время” отключает навигацию и охватывает всю историю
  - Индикатор загрузки при запросах из БД
  - Комpaktная строка времени и мини‑шкала
- Контроль производительности:
  - Лимит точек на графике (по умолчанию 1000) с прореживанием на сервере
  - Кнопка аппроксимации (простое сглаживание окном 3)
- Настройки: порт сервера, NTP, лимит точек, ссылки на репозиторий/протокол
- Опциональный встроенный NTP‑сервер (UDP 123)
- Просмотр «JSON Data»

### Технологии
- Python: FastAPI, Uvicorn, sqlite3, PySide6, socketserver (NTP)
- Frontend: Chart.js, chartjs-adapter-date-fns, чистый JS и CSS
- База: SQLite файл `thermogrid.db`

### Структура проекта (основное)
- `main.py` — точка входа (FastAPI, трей, NTP, БД, маршруты)
- `index.html` — разметка UI
- `static/app.js`, `static/style.css` — логика/стили фронтенда
- `thermogrid.db` — SQLite БД (создаётся/используется при работе)
- `init_db.py`, `update_db_structure.py` — вспомогательные скрипты БД
- `device_simulator.py` — пример симулятора (опц.)
- `backups/` — архивы и копии БД
- `reference/` — референсные/наследованные UI (PyQt)

### Модель данных
- `devices(...)`, `sensors(...)`, `readings(...)`, `settings(key, value)`

### API
- GET `/api/devices` — список устройств
- GET `/api/device/{id}` — детали устройства и сенсоры
- POST `/api/history` — история показаний по сенсору
  - Тело: `{ device_id, sensor_id, start_time?, end_time?, max_points? }`
  - Ответ: `[ { timestamp, temperature_c }, ... ]`
  - Прореживание: сервер равномерно уменьшает число точек до `max_points` (по умолчанию 1000)
- GET `/api/settings` — `server_ip`, `server_port`, `ntp_enabled`, `max_points`, `app_version`, `repo_url`, `json_protocol_url`, `developer`
- POST `/api/settings` — сохраняет `server_port`, `ntp_enabled`, `max_points`, `repo_url`, `json_protocol_url`

### Особенности фронтенда
- Кроссхер рисуется на канвасе (без DOM‑ползунка); красная пунктирная линия с треугольником снизу. Тонкие серые пунктиры отмечают границы суток.
- Клик/перетаскивание двигают линию; карточки показывают ближайшие значения по времени. Через 5 секунд бездействия — возврат к последней точке.
- Смена периода пересоздаёт график; для всех периодов, кроме «Всё время», диапазон привязан к последнему времени данных.

### Настройки и производительность
- Лимит точек: по умолчанию 1000; минимум 100; применяется на сервере при каждом запросе истории.
- Аппроксимация: сглаживание скользящим средним (окно 3) на стороне клиента.
- NTP: опционально; включается в настройках; порт 123 (требуются права администратора для бинда).

### Запуск (Windows, PowerShell)
Требования:
- Python 3.10+
- Пакеты: fastapi, uvicorn, PySide6

Шаги:
1) Установка зависимостей (пример):
```
py -m pip install fastapi uvicorn PySide6
```
2) Запуск сервера:
```
py main.py
```
3) Браузер откроется автоматически. Если нет — откройте адрес, указанный в логе (по умолчанию http://127.0.0.1:9090). В «Настройках» отображается реальный IP этого компьютера.

### О программе
- Отображается: версия, IP сервера, ссылка на репозиторий, ссылка на JSON‑протокол, разработчик (Serbinov Oleg), подсказки по производительности.

---

If you need more details, open an issue or extend this document.

### Build a small one-file EXE (Windows)
- Use the headless entrypoint to avoid bundling PySide6:
  - server_headless.py exposes the same API and UI in the browser, without tray.
- From an activated venv run one of:
  - PowerShell: `./build_exe.ps1` (optionally add `-UseUPX` if UPX is installed)
  - CMD: `build_exe.bat`
- Output will be placed in `WIN_64/ThermoGridServer.exe`.
- Notes for minimal size:
  - Excludes: PySide6, GUI libs, scientific libs; only FastAPI/Uvicorn/SQLite are bundled.
  - With UPX you can reduce a few more MB.
