# file: main.py
import sys, webbrowser, threading, os, logging, sqlite3, time, json, socket, struct, socketserver
from uvicorn import Config, Server
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QIcon, QAction
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# --- Logging & Config ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
APP_NAME = "ThermoGridServer"
APP_VERSION = "0.1.0"
HOST = "0.0.0.0"  # Слушать на всех сетевых интерфейсах
DB_NAME = "thermogrid.db"
BASE_URL = "" # Будет определен в main()
BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else sys._MEIPASS
NTP_PORT = 123

# --- Database ---
def initialize_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY, deviceName TEXT, last_seen INTEGER, firmware_version TEXT, uptime_ms INTEGER,
            alarm_active BOOLEAN, alarm_threshold_c REAL, network TEXT, ip_address TEXT, lat REAL, lon REAL,
            raw_json TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS sensors (
            device_id TEXT, sensor_id INTEGER, name TEXT, type TEXT,
            temperature REAL, humidity REAL, last_reading_time INTEGER,
            PRIMARY KEY(device_id, sensor_id)
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS readings (
            device_id TEXT, sensor_id INTEGER, timestamp INTEGER, temperature_c REAL, humidity REAL
        )""")
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()

def get_setting(key, default=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        return row[0] if row else default

def set_setting(key, value):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()

def save_device_data(data):
    device_id = data.get('deviceId')
    if not device_id: return logging.error(f"DATABASE: 'deviceId' не найден в данных: {data}")
    
    status = data.get('status', {})
    geo = data.get('geo', {})
    device_info = (
        device_id, data.get('deviceName'), int(time.time()), data.get('firmware_version'), data.get('uptime_ms'),
        status.get('alarm_active'), status.get('alarm_threshold_c'), status.get('network'), status.get('ip_address'),
        geo.get('lat'), geo.get('lon'), json.dumps(data)
    )
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", device_info)
        for s_data in data.get('sensors', []):
            sensor_id = s_data.get('id')
            if sensor_id is None: continue
            timestamp = int(time.time())
            readings = s_data.get('data', {})
            temp_value = readings.get('temperature_c')
            humidity_value = readings.get('humidity')
            
            # Обновляем данные в таблице sensors (включая последние показания)
            c.execute("""
                INSERT OR REPLACE INTO sensors 
                (device_id, sensor_id, name, type, temperature, humidity, last_reading_time) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (device_id, sensor_id, s_data.get('name'), s_data.get('type'), 
                 temp_value, humidity_value, timestamp))
            
            # Записываем в историю показаний
            if 'temperature_c' in readings:
                c.execute("INSERT INTO readings (device_id, sensor_id, timestamp, temperature_c, humidity) VALUES (?, ?, ?, ?, ?)",
                          (device_id, sensor_id, timestamp, temp_value, humidity_value))
        conn.commit()

def get_devices():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, deviceName, ip_address, alarm_active, last_seen FROM devices ORDER BY last_seen DESC")
        return [dict(row) for row in c.fetchall()]

def get_device_details(device_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM devices WHERE id=?", (device_id,))
        device = dict(c.fetchone())
        c.execute("SELECT sensor_id, name, type FROM sensors WHERE device_id=?", (device_id,))
        device['sensors'] = [dict(row) for row in c.fetchall()]
        for s in device['sensors']:
            # Используем температуру, влажность и время из таблицы sensors
            c.execute("SELECT temperature, humidity, last_reading_time FROM sensors WHERE device_id=? AND sensor_id=?", (device_id, s['sensor_id']))
            row = c.fetchone()
            s['latest_temperature'] = row['temperature'] if row else None
            s['latest_humidity'] = row['humidity'] if row else None
            s['last_reading_time'] = row['last_reading_time'] if row else None
        return device

def get_readings_history(device_id, sensor_id, start_time=None, end_time=None, limit=1000, max_points=None):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        def downsample(points, max_pts):
            if max_pts is None: return points
            try:
                max_pts = int(max_pts)
            except Exception:
                return points
            n = len(points)
            if n <= max_pts or max_pts <= 0:
                return points
            # Равномерное прореживание: всегда сохраняем первую и последнюю точки
            step = max(1, n // max_pts)
            sampled = [points[i] for i in range(0, n, step)]
            if sampled[-1] != points[-1]:
                sampled.append(points[-1])
            return sampled

        # Если указаны временные границы, используем их
        if start_time is not None and end_time is not None:
            logging.info(f"История: запрос за период {start_time} - {end_time} для {device_id}:{sensor_id}")
            c.execute(
                "SELECT timestamp, temperature_c FROM readings WHERE device_id=? AND sensor_id=? AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC", 
                (device_id, sensor_id, start_time, end_time)
            )
            rows = [dict(row) for row in c.fetchall()]
            if max_points is None:
                try:
                    max_points = int(get_setting('max_points', '1000'))
                except Exception:
                    max_points = 1000
            return downsample(rows, max_points)
        else:
            logging.info(f"История: запрос последних {limit} записей для {device_id}:{sensor_id}")
            c.execute(
                "SELECT timestamp, temperature_c FROM readings WHERE device_id=? AND sensor_id=? ORDER BY timestamp DESC LIMIT ?", 
                (device_id, sensor_id, limit)
            )
            rows = [dict(row) for row in c.fetchall()][::-1]  # в возрастающем порядке
            if max_points is None:
                try:
                    max_points = int(get_setting('max_points', '1000'))
                except Exception:
                    max_points = 1000
            return downsample(rows, max_points)

# --- NTP Server ---
class NTPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        NTP_EPOCH_OFFSET = 2208988800
        data, sock = self.request
        if len(data) < 48: return
        transmit_time = int(time.time()) + NTP_EPOCH_OFFSET
        resp = bytearray(48); resp[0] = 0b00100100
        struct.pack_into("!I", resp, 40, transmit_time)
        sock.sendto(resp, self.client_address)

class NtpServerWorker(QObject):
    log_message = Signal(str)
    def __init__(self, host, port): super().__init__(); self.host, self.port, self.server = host, port, None
    def run(self):
        try:
            self.server = socketserver.UDPServer((self.host, self.port), NTPRequestHandler)
            self.log_message.emit(f"NTP server started on {self.host}:{self.port}")
            self.server.serve_forever()
        except Exception as e: self.log_message.emit(f"NTP Server Error: {e}")
    def shutdown(self):
        if self.server: self.server.shutdown(); self.server.server_close(); self.log_message.emit("NTP server stopped.")

# --- Application Manager (for background tasks) ---
class ApplicationManager(QObject):
    settings_changed = Signal()
    def __init__(self):
        super().__init__()
        self.ntp_server_thread, self.ntp_worker = None, None
        self.settings_changed.connect(self.check_and_manage_ntp_server)
    @Slot()
    def check_and_manage_ntp_server(self):
        ntp_enabled = get_setting('ntp_enabled', 'false') == 'true'
        is_running = self.ntp_server_thread is not None and self.ntp_server_thread.isRunning()
        if ntp_enabled and not is_running:
            logging.info("NTP: Starting server...")
            try:
                self.ntp_server_thread = QThread()
                self.ntp_worker = NtpServerWorker(host=HOST, port=NTP_PORT)
                self.ntp_worker.moveToThread(self.ntp_server_thread)
                self.ntp_worker.log_message.connect(lambda msg: logging.info(f"[NTP] {msg}"))
                self.ntp_server_thread.started.connect(self.ntp_worker.run)
                self.ntp_server_thread.start()
            except Exception as e: logging.error(f"NTP: Failed to start: {e}")
        elif not ntp_enabled and is_running:
            logging.info("NTP: Stopping server..."); self.shutdown_ntp_worker()
    def shutdown_ntp_worker(self):
        if self.ntp_server_thread:
            if self.ntp_worker: self.ntp_worker.shutdown()
            if self.ntp_server_thread.isRunning(): self.ntp_server_thread.quit(); self.ntp_server_thread.wait(2000)
            self.ntp_server_thread, self.ntp_worker = None, None

# --- FastAPI ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    with open("index.html", encoding="utf-8") as f: return f.read()

@app.post("/")
def api_root_post(data: dict): save_device_data(data); return {"status": "ok"}

@app.get("/api/devices")
def api_get_devices(): return get_devices()

@app.get("/api/device/{device_id}")
def api_get_device_details(device_id: str): return get_device_details(device_id)

@app.post("/api/history")
async def api_get_history(request: Request): 
    req = await request.json()
    return get_readings_history(
        req['device_id'], 
        req['sensor_id'],
        start_time=req.get('start_time'),
    end_time=req.get('end_time'),
    max_points=req.get('max_points')
    )

@app.get("/api/settings")
def api_get_settings():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
    return {
        "server_ip": ip,
        "server_port": get_setting("server_port", "9090"),
        "ntp_enabled": get_setting("ntp_enabled", "false") == "true",
        "max_points": int(get_setting("max_points", "1000") or 1000),
        "app_version": APP_VERSION,
        "repo_url": get_setting("repo_url", ""),
        "json_protocol_url": get_setting("json_protocol_url", "/static/json_protocol.html"),
        "developer": "Serbinov Oleg"
    }

@app.post("/api/settings")
async def api_set_settings(request: Request):
    settings = await request.json()
    if 'server_port' in settings: set_setting('server_port', settings['server_port'])
    if 'ntp_enabled' in settings: set_setting('ntp_enabled', "true" if settings['ntp_enabled'] else "false")
    if 'max_points' in settings:
        try:
            mp = int(settings['max_points'])
            if mp < 100: mp = 100
            set_setting('max_points', mp)
        except Exception:
            pass
    if 'repo_url' in settings:
        try:
            set_setting('repo_url', settings['repo_url'])
        except Exception:
            pass
    if 'json_protocol_url' in settings:
        try:
            set_setting('json_protocol_url', settings['json_protocol_url'])
        except Exception:
            pass
    if hasattr(request.app.state, 'settings_changed_callback'): request.app.state.settings_changed_callback()
    logging.info(f"SETTINGS: Сохранены настройки: {settings}")
    return {"status": "ok", "message": "Settings saved! Port change requires server restart."}

# --- Main Application ---
def open_in_browser():
    try: webbrowser.open(BASE_URL); logging.info(f"Opened {BASE_URL} in browser.")
    except Exception as e: logging.error(f"Failed to open browser: {e}")

def main():
    global BASE_URL
    initialize_db()
    server_port = int(get_setting("server_port", "9090"))
    BASE_URL = f"http://127.0.0.1:{server_port}"
    qt_app = QApplication(sys.argv)
    qt_app.setQuitOnLastWindowClosed(False)
    app_manager = ApplicationManager()
    app.state.settings_changed_callback = app_manager.settings_changed.emit
    app_manager.check_and_manage_ntp_server()
    config = Config(app=app, host=HOST, port=server_port, log_level="warning")
    server = Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    def shutdown_web_server(): server.should_exit = True; server_thread.join(timeout=5)
    qt_app.aboutToQuit.connect(app_manager.shutdown_ntp_worker)
    qt_app.aboutToQuit.connect(shutdown_web_server)
    icon_path = os.path.join(BUNDLE_DIR, "icons", "app_icon.svg")
    tray_icon = QSystemTrayIcon(QIcon(icon_path) if os.path.exists(icon_path) else qt_app.style().standardIcon(QStyle.SP_ComputerIcon), parent=qt_app)
    tray_icon.setToolTip(APP_NAME)
    menu = QMenu(); open_action = QAction("Open in Browser"); open_action.triggered.connect(open_in_browser); menu.addAction(open_action)
    menu.addSeparator(); quit_action = QAction("Quit"); quit_action.triggered.connect(qt_app.quit); menu.addAction(quit_action)
    tray_icon.setContextMenu(menu); tray_icon.show()
    tray_icon.activated.connect(lambda reason: open_in_browser() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    open_in_browser()
    sys.exit(qt_app.exec())

if __name__ == "__main__":
    main()