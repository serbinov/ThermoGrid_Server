# file: database.py
import sqlite3, json, time

DB_NAME = 'thermogrid.db'
ALARM_LOG_FILE = 'alarms.log'

def initialize_db():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    # ИЗМЕНЕНИЕ: Добавлены поля ip_address и alarm_threshold
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY, 
            display_name TEXT, 
            last_seen INTEGER, 
            firmware_version TEXT,
            ip_address TEXT,
            alarm_threshold REAL
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            device_id TEXT,
            sensor_id_on_device INTEGER, 
            name_from_device TEXT,
            display_name TEXT,
            FOREIGN KEY (device_id) REFERENCES devices (id)
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sensor_db_id INTEGER,
            timestamp INTEGER, data TEXT,
            FOREIGN KEY (sensor_db_id) REFERENCES sensors (id)
        )''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alarm_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT, target_device_id TEXT,
            target_sensor_name TEXT, data_key TEXT, condition TEXT, value REAL,
            action_type TEXT DEFAULT 'notification'
        )''')
    conn.commit(); conn.close()

def process_incoming_data(data_dict):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    device_id = data_dict['deviceId']; timestamp = data_dict['timestamp_utc']
    
    # ИЗМЕНЕНИЕ: Извлекаем новые поля из JSON
    status = data_dict.get('status', {})
    ip_address = status.get('ip_address')
    alarm_threshold = status.get('alarm_threshold_c')
    firmware_version = data_dict.get('firmware_version')
    
    # ИЗМЕНЕНИЕ: Используем deviceName из JSON как display_name по умолчанию, иначе deviceId
    display_name_on_first_seen = data_dict.get('deviceName', device_id)
    cursor.execute(
        "INSERT OR IGNORE INTO devices (id, display_name, last_seen, firmware_version, ip_address, alarm_threshold) VALUES (?, ?, ?, ?, ?, ?)",
        (device_id, display_name_on_first_seen, int(time.time()), firmware_version, ip_address, alarm_threshold)
    )
    # ИЗМЕНЕНИЕ: Обновляем все изменяемые поля при каждом пакете
    cursor.execute(
        "UPDATE devices SET last_seen = ?, firmware_version = ?, ip_address = ?, alarm_threshold = ? WHERE id = ?",
        (int(time.time()), firmware_version, ip_address, alarm_threshold, device_id)
    )
    
    for sensor_data in data_dict['sensors']:
        sensor_id_on_device = sensor_data['id']; sensor_name = sensor_data['name']
        cursor.execute("SELECT id FROM sensors WHERE device_id = ? AND sensor_id_on_device = ?", (device_id, sensor_id_on_device))
        result = cursor.fetchone()
        if result:
            sensor_db_id = result[0]
            cursor.execute("UPDATE sensors SET name_from_device = ? WHERE id = ?", (sensor_name, sensor_db_id))
        else:
            cursor.execute(
                "INSERT INTO sensors (device_id, sensor_id_on_device, name_from_device, display_name) VALUES (?, ?, ?, ?)",
                (device_id, sensor_id_on_device, sensor_name, sensor_name)
            )
            sensor_db_id = cursor.lastrowid
        
        readings_data_json = json.dumps(sensor_data['data'])
        cursor.execute("INSERT INTO readings (sensor_db_id, timestamp, data) VALUES (?, ?, ?)", (sensor_db_id, timestamp, readings_data_json))
    
    conn.commit(); conn.close()
    print(f"БД: Данные для {device_id} обработаны.")

def get_readings_for_sensor(device_id, sensor_id_on_device):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    cursor.execute("SELECT id FROM sensors WHERE device_id = ? AND sensor_id_on_device = ?", (device_id, sensor_id_on_device))
    sensor_row = cursor.fetchone()
    if not sensor_row: conn.close(); return []
    sensor_db_id = sensor_row['id']
    cursor.execute("SELECT timestamp, data FROM readings WHERE sensor_db_id = ? ORDER BY timestamp ASC", (sensor_db_id,))
    readings = cursor.fetchall(); conn.close()
    return [(row['timestamp'], json.loads(row['data'])) for row in readings]

def get_device_display_name(device_id):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("SELECT display_name FROM devices WHERE id = ?", (device_id,))
    result = cursor.fetchone(); conn.close()
    return result[0] if result else device_id

def update_device_display_name(device_id, new_name):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("UPDATE devices SET display_name = ? WHERE id = ?", (new_name, device_id))
    conn.commit(); conn.close()

def get_sensor_display_name(device_id, sensor_id_on_device):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute(
        "SELECT display_name FROM sensors WHERE device_id = ? AND sensor_id_on_device = ?",
        (device_id, sensor_id_on_device)
    )
    result = cursor.fetchone(); conn.close()
    return result[0] if result else None

def update_sensor_display_name(device_id, sensor_id_on_device, new_name):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute(
        "UPDATE sensors SET display_name = ? WHERE device_id = ? AND sensor_id_on_device = ?",
        (new_name, device_id, sensor_id_on_device)
    )
    conn.commit(); conn.close()

def get_all_alarm_rules():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    cursor.execute("SELECT * FROM alarm_rules"); rules = [dict(row) for row in cursor.fetchall()]; conn.close(); return rules

def add_alarm_rule(target_device, target_sensor, data_key, condition, value, action_type):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO alarm_rules (target_device_id, target_sensor_name, data_key, condition, value, action_type) VALUES (?, ?, ?, ?, ?, ?)",
        (target_device, target_sensor, data_key, condition, value, action_type)
    )
    conn.commit(); conn.close()

def remove_alarm_rule(rule_id):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("DELETE FROM alarm_rules WHERE id = ?", (rule_id,)); conn.commit(); conn.close()

def log_alarm_to_file(message):
    with open(ALARM_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")