"""
Headless entrypoint for ThermoGrid Server (no PySide6), suitable for a small one-file EXE.

- Serves the same FastAPI app and endpoints as the tray version.
- Uses server receive timestamps for readings, same DB schema.
- Optional NTP UDP server controlled by settings.ntp_enabled (no Qt).
"""
import os, sys, time, json, logging, sqlite3, threading, struct, socketserver, webbrowser
from uvicorn import Config, Server
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Logging to file when frozen without console
try:
    if getattr(sys, 'stderr', None) is None:
        logging.basicConfig(
            level=logging.INFO,
            filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'thermogrid.log'),
            filemode='a',
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
except Exception:
    logging.basicConfig(level=logging.INFO)

APP_NAME = "ThermoGridServer"
APP_VERSION = "0.1.0"
HOST = "0.0.0.0"
DB_NAME = "thermogrid.db"
BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else sys._MEIPASS
NTP_PORT = 123

# --- Database helpers ---
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
    if not device_id:
        logging.error("DATABASE: 'deviceId' not found in payload")
        return
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
            if sensor_id is None:
                continue
            timestamp = int(time.time())
            readings = s_data.get('data', {})
            temp_value = readings.get('temperature_c')
            humidity_value = readings.get('humidity')
            c.execute(
                """
                INSERT OR REPLACE INTO sensors (device_id, sensor_id, name, type, temperature, humidity, last_reading_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (device_id, sensor_id, s_data.get('name'), s_data.get('type'), temp_value, humidity_value, timestamp)
            )
            if 'temperature_c' in readings:
                c.execute(
                    "INSERT INTO readings (device_id, sensor_id, timestamp, temperature_c, humidity) VALUES (?, ?, ?, ?, ?)",
                    (device_id, sensor_id, timestamp, temp_value, humidity_value)
                )
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
        device_row = c.fetchone()
        device = dict(device_row) if device_row else {"id": device_id}
        c.execute("SELECT sensor_id, name, type FROM sensors WHERE device_id=?", (device_id,))
        device['sensors'] = [dict(row) for row in c.fetchall()]
        for s in device['sensors']:
            c.execute(
                "SELECT temperature, humidity, last_reading_time FROM sensors WHERE device_id=? AND sensor_id=?",
                (device_id, s['sensor_id'])
            )
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
            if max_pts is None:
                return points
            try:
                max_pts = int(max_pts)
            except Exception:
                return points
            n = len(points)
            if n <= max_pts or max_pts <= 0:
                return points
            step = max(1, n // max_pts)
            sampled = [points[i] for i in range(0, n, step)]
            if sampled[-1] != points[-1]:
                sampled.append(points[-1])
            return sampled
        if start_time is not None and end_time is not None:
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
            c.execute(
                "SELECT timestamp, temperature_c FROM readings WHERE device_id=? AND sensor_id=? ORDER BY timestamp DESC LIMIT ?",
                (device_id, sensor_id, limit)
            )
            rows = [dict(row) for row in c.fetchall()][::-1]
            if max_points is None:
                try:
                    max_points = int(get_setting('max_points', '1000'))
                except Exception:
                    max_points = 1000
            return downsample(rows, max_points)

def get_device_time_range(device_id: str):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM readings WHERE device_id=?", (device_id,))
        row = c.fetchone()
        if not row or (row[0] is None and row[1] is None):
            return {"min": None, "max": None}
        return {"min": int(row[0]) if row[0] is not None else None,
                "max": int(row[1]) if row[1] is not None else None}

# --- NTP server (no Qt) ---
class NTPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        NTP_EPOCH_OFFSET = 2208988800
        data, sock = self.request
        if len(data) < 48:
            return
        transmit_time = int(time.time()) + NTP_EPOCH_OFFSET
        resp = bytearray(48)
        resp[0] = 0b00100100
        struct.pack_into("!I", resp, 40, transmit_time)
        sock.sendto(resp, self.client_address)

def start_ntp_server_in_thread(host: str, port: int):
    def worker():
        try:
            with socketserver.UDPServer((host, port), NTPRequestHandler) as server:
                logging.info(f"NTP server started on {host}:{port}")
                server.serve_forever()
        except Exception as e:
            logging.error(f"NTP server error: {e}")
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return t

# --- FastAPI app ---
app = FastAPI()
app.mount("/static", StaticFiles(directory=os.path.join(BUNDLE_DIR, "static")), name="static")
app.mount("/icons", StaticFiles(directory=os.path.join(BUNDLE_DIR, "icons")), name="icons")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    ico_path = os.path.join(BUNDLE_DIR, "icons", "app_icon.ico")
    if os.path.exists(ico_path):
        return FileResponse(ico_path)
    try:
        for name in os.listdir(os.path.join(BUNDLE_DIR, "icons")):
            if name.lower().endswith('.ico'):
                return FileResponse(os.path.join(BUNDLE_DIR, "icons", name))
    except Exception:
        pass
    return JSONResponse({"detail": "favicon not found"}, status_code=404)

@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(BUNDLE_DIR, "index.html")
    with open(index_path, encoding="utf-8") as f:
        return f.read()

@app.post("/")
def api_root_post(data: dict):
    save_device_data(data)
    return {"status": "ok"}

@app.get("/api/devices")
def api_get_devices():
    return get_devices()

@app.get("/api/device/{device_id}")
def api_get_device_details(device_id: str):
    return get_device_details(device_id)

@app.get("/api/device_range/{device_id}")
def api_get_device_time_range(device_id: str):
    return get_device_time_range(device_id)

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
    return {
        "server_port": get_setting("server_port", "9090"),
        "ntp_enabled": get_setting("ntp_enabled", "false") == "true",
        "max_points": int(get_setting("max_points", "1000") or 1000),
        "app_version": APP_VERSION,
        "developer": "Serbinov Oleg"
    }

@app.post("/api/settings")
async def api_set_settings(request: Request):
    settings = await request.json()
    if 'server_port' in settings:
        set_setting('server_port', settings['server_port'])
    if 'ntp_enabled' in settings:
        set_setting('ntp_enabled', "true" if settings['ntp_enabled'] else "false")
    if 'max_points' in settings:
        try:
            mp = int(settings['max_points'])
            if mp < 100:
                mp = 100
            set_setting('max_points', mp)
        except Exception:
            pass
    logging.info(f"SETTINGS: Saved: {settings}")
    return {"status": "ok", "message": "Settings saved! Port change requires server restart."}


def open_in_browser(url: str):
    try:
        webbrowser.open(url)
    except Exception as e:
        logging.error(f"Failed to open browser: {e}")


def run():
    initialize_db()
    server_port = int(get_setting("server_port", "9090"))
    base_url = f"http://127.0.0.1:{server_port}"
    # Start NTP server if enabled
    if get_setting('ntp_enabled', 'false') == 'true':
        start_ntp_server_in_thread(HOST, NTP_PORT)
    # Uvicorn server in a background thread
    config = Config(app=app, host=HOST, port=server_port, log_level="warning", log_config=None, access_log=False)
    server = Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    # Give server a moment to start
    time.sleep(0.5)
    open_in_browser(base_url)
    # Block main thread until server stops
    try:
        while t.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        server.should_exit = True
        t.join(timeout=5)


if __name__ == "__main__":
    run()
