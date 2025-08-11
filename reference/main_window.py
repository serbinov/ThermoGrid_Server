# file: main_window.py
import sys, time, os
from datetime import datetime

from PySide6.QtWidgets import (QMainWindow, QTreeWidgetItem, QTableWidgetItem, QMessageBox, QInputDialog, QSystemTrayIcon, QMenu, QStyle, QGroupBox, QVBoxLayout, QLabel, QFormLayout, QHBoxLayout, QApplication)
from PySide6.QtCore import (Signal, Slot, QThread, QTimer, QSettings, Qt)
from PySide6.QtGui import (QIcon, QColor, QAction)
from pynotifier import Notification
import autolaunch

from main_ui_coded import Ui_MainWindow
from alarm_dialog import AlarmDialog
from database import *
from device_delegate import DeviceDelegate
from network import ServerWorker
from config import *
from utils import format_uptime

class MainWindow(QMainWindow):
    notification_request = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.device_items = {}
        self.alarm_rules = []
        self.currently_selected_item = None
        
        self._setup_styles()
        self._setup_ui_components()
        self._connect_signals()
        
        self.server_thread = None
        self.server_worker = None
        self.start_server()
        
        self.status_check_timer = QTimer(self)
        self.status_check_timer.timeout.connect(self.check_device_statuses)
        self.status_check_timer.start(10000)
        
        self.load_and_display_alarm_rules()
        self.load_devices_from_db()

        if self.ui.deviceTreeWidget.topLevelItemCount() > 0:
            first_item = self.ui.deviceTreeWidget.topLevelItem(0)
            self.log("Автоматический выбор первого устройства при запуске.")
            QTimer.singleShot(100, lambda: self.auto_select_item(first_item))

        if self.settings.value("startInTray", False, type=bool):
            self.log("Приложение запущено в свернутом режиме.")
        else:
            self.show()

    # --- Setup Methods ---
    def _setup_styles(self):
        self.card_style = "QGroupBox { background-color: #2E3B4E; border: 1px solid #4F627B; border-radius: 5px; margin-top: 15px; } QGroupBox::title { subcontrol-origin: margin; padding: 2px 8px; color: #E0E0E0; font-size: 9pt; } QLabel { color: #E0E0E0; font-size: 9pt; }"
        self.status_card_title_style = "QGroupBox::title { subcontrol-position: top center; background-color: #4F627B; border-radius: 3px; color: #FFFFFF; font-weight: bold; }"
        self.sensor_card_title_style = "QGroupBox::title { subcontrol-position: top left; }"
    
    def _setup_ui_components(self):
        app_icon = QIcon(os.path.join(BASE_DIR, 'icons', 'app_icon.svg'))
        self.setWindowIcon(app_icon)
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        
        self.icons = {
            'online': QIcon(os.path.join(BASE_DIR, 'icons', 'device_online.svg')),
            'offline': QIcon(os.path.join(BASE_DIR, 'icons', 'device_offline.svg')),
            'temp': QIcon(os.path.join(BASE_DIR, 'icons', 'thermometer.svg')),
            'humidity': QIcon(os.path.join(BASE_DIR, 'icons', 'humidity.svg'))
        }
        
        self.device_delegate = DeviceDelegate(self.ui.deviceTreeWidget)
        self.ui.deviceTreeWidget.setItemDelegate(self.device_delegate)
        self.ui.deviceTreeWidget.setIndentation(10)
        self.ui.deviceTreeWidget.setColumnCount(1)
        self.ui.deviceTreeWidget.expandAll()
        
        self.setup_tray_icon()
        self.setup_settings()
        
    def _connect_signals(self):
        self.ui.addAlarmButton.clicked.connect(self.on_add_alarm)
        self.ui.removeAlarmButton.clicked.connect(self.on_remove_alarm)
        self.notification_request.connect(self.show_notification)
        self.ui.deviceTreeWidget.itemClicked.connect(self.on_tree_item_clicked)
        self.ui.deviceTreeWidget.itemDoubleClicked.connect(self.on_tree_item_double_clicked)
        self.ui.timeScrollBar.valueChanged.connect(self.on_time_scroll)
        
    # --- Network and Server ---
    def start_server(self):
        if self.server_thread and self.server_thread.isRunning(): return
        server_port = self.settings.value("serverPort", 8080, type=int)
        self.server_thread = QThread()
        self.server_worker = ServerWorker("0.0.0.0", server_port)
        self.server_worker.moveToThread(self.server_thread)
        self.server_thread.started.connect(self.server_worker.run)
        self.server_worker.data_received.connect(self.handle_incoming_data)
        self.server_worker.log_message.connect(self.log)
        self.server_thread.start()
        self.log(f"Поток сервера запущен для порта {server_port}")

    @Slot()
    def restart_server(self):
        self.log("Начало перезапуска сервера...")
        if self.server_worker: self.server_worker.shutdown()
        if self.server_thread: self.server_thread.quit(); self.server_thread.wait(5000)
        self.log("Старый поток сервера остановлен. Запускаем новый...")
        QTimer.singleShot(1000, self.start_server)
        
    # --- System Tray and Settings ---
    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        show_action = QAction("Показать", self); quit_action = QAction("Выход", self)
        show_action.triggered.connect(self.show_normal); quit_action.triggered.connect(self.quit_application)
        tray_menu = QMenu(); tray_menu.addAction(show_action); tray_menu.addSeparator(); tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu); self.tray_icon.show(); self.tray_icon.activated.connect(self.on_tray_icon_activated)

    def setup_settings(self):
        self.settings = QSettings("MyCompany", APP_NAME)
        try: self.ui.autostartCheckBox.setChecked(autolaunch.is_enabled(APP_NAME))
        except Exception as e: self.log(f"Не удалось проверить статус автозапуска: {e}"); self.ui.autostartCheckBox.setEnabled(False) 
        self.ui.startInTrayCheckBox.setChecked(self.settings.value("startInTray", False, type=bool))
        self.ui.portSpinBox.setValue(self.settings.value("serverPort", 8080, type=int))
        self.ui.autostartCheckBox.stateChanged.connect(self.on_autostart_changed)
        self.ui.startInTrayCheckBox.stateChanged.connect(self.on_startintray_changed)
        self.ui.applyNetworkSettingsButton.clicked.connect(self.on_apply_network_settings)

    @Slot()
    def on_apply_network_settings(self):
        new_port = self.ui.portSpinBox.value()
        self.settings.setValue("serverPort", new_port)
        self.log(f"Порт сервера изменен на {new_port}. Перезапускаем сервер...")
        QMessageBox.information(self, "Перезапуск сервера", "Настройки сети применены. Сервер будет перезапущен.")
        self.restart_server()

    @Slot(int)
    def on_autostart_changed(self, state):
        is_enabled = state == Qt.CheckState.Checked.value
        try:
            app_path=sys.executable
            app_args=''
            if'.py'in app_path or'.pyw'in app_path:
                script_path=os.path.abspath(__file__)
                app_args=f'"{script_path}"'
            if is_enabled:
                autolaunch.enable(APP_NAME,app_path,app_args)
                self.log("Автозапуск включен.")
            else:
                autolaunch.disable(APP_NAME)
                self.log("Автозапуск выключен.")
            self.settings.setValue("autostart",is_enabled)
        except Exception as e:
            self.log(f"Ошибка при изменении автозапуска: {e}")
            QMessageBox.critical(self,"Ошибка",f"Не удалось изменить настройку автозапуска:\n{e}")
            self.ui.autostartCheckBox.setChecked(not is_enabled)

    @Slot(int)
    def on_startintray_changed(self, state):
        is_enabled = state == Qt.CheckState.Checked.value
        self.settings.setValue("startInTray",is_enabled)
        self.log(f"Настройка 'Запускать свернутым' {'включена' if is_enabled else 'выключена'}.")

    # --- Window Events ---
    def show_normal(self): self.show(); self.activateWindow(); self.raise_()
    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick: self.show_normal()
    def closeEvent(self,event):
        event.ignore(); self.hide()
        self.tray_icon.showMessage("Приложение свернуто","ThermoGrid Server продолжает работать в фоновом режиме.",QSystemTrayIcon.MessageIcon.Information,2000)
    def showEvent(self, event): super().showEvent(event)
    def quit_application(self):
        self.log("Приложение закрывается...")
        if self.server_worker: self.server_worker.shutdown()
        if self.server_thread: self.server_thread.quit(); self.server_thread.wait(5000)
        self.tray_icon.hide(); QApplication.instance().quit()
        
    # --- Data Handling and DB ---
    def load_devices_from_db(self):
        conn=sqlite3.connect(DB_NAME); conn.row_factory=sqlite3.Row; cursor=conn.cursor()
        cursor.execute("SELECT * FROM devices"); devices=cursor.fetchall()
        for device_row in devices:
            device_keys = device_row.keys() 
            device_id=device_row['id']
            fake_data_packet={
                'deviceId': device_id, 'deviceName': device_row['display_name'],
                'last_seen': device_row['last_seen'],
                'firmware_version': device_row['firmware_version'] if 'firmware_version' in device_keys else 'N/A',
                'uptime_ms': None, 'geo': {}, 
                'status': {
                    'ip_address': device_row['ip_address'] if 'ip_address' in device_keys else 'N/A',
                    'alarm_threshold_c': device_row['alarm_threshold'] if 'alarm_threshold' in device_keys else None,
                    'alarm_active': None, 'network': None },
                'sensors':[]
            }
            cursor.execute("SELECT * FROM sensors WHERE device_id = ?",(device_id,))
            sensors=cursor.fetchall()
            for sensor_row in sensors:
                fake_data_packet['sensors'].append({'id':sensor_row['sensor_id_on_device'],'name':sensor_row['name_from_device'],'display_name':sensor_row['display_name'],'data':{}})
            self.update_tree_and_db(fake_data_packet,from_db=True)
        conn.close()
        self.ui.deviceTreeWidget.expandAll()

    @Slot(dict,bool)
    def handle_incoming_data(self,data,from_db=False):
        is_first_device = data['deviceId'] not in self.device_items and len(self.device_items) == 0
        self.update_tree_and_db(data,from_db)
        if is_first_device and not from_db:
            self.log(f"Получены данные от первого устройства ({data['deviceId']}). Выбираю его автоматически.")
            new_item = self.device_items[data['deviceId']]
            QTimer.singleShot(100, lambda: self.auto_select_item(new_item))
        if not from_db:
            self.check_alarms(data)
            if self.currently_selected_item:
                selected_info = self._get_selected_item_info(self.currently_selected_item)
                if data['deviceId'] == selected_info.get('device_id'):
                    self.log(f"Данные для открытого графика {selected_info['device_id']} обновились. Перерисовываю...")
                    self.on_tree_item_clicked(self.currently_selected_item, 0)
    
    @Slot(QTreeWidgetItem)
    def auto_select_item(self, item):
        self.ui.deviceTreeWidget.setCurrentItem(item)
        self.on_tree_item_clicked(item, 0)

    def _create_device_item(self, data):
        device_id = data['deviceId']
        display_name = get_device_display_name(device_id)
        device_item = QTreeWidgetItem(self.ui.deviceTreeWidget)
        device_item.setText(0, f"{display_name}")
        device_item.setIcon(0, self.icons['online'])
        device_item.setData(0, Qt.ItemDataRole.UserRole, data)
        device_item.setExpanded(True)
        self.device_items[device_id] = device_item
        for sensor_data in data['sensors']:
            sensor_display_name = get_sensor_display_name(device_id, sensor_data['id']) or sensor_data['name']
            sensor_item = QTreeWidgetItem(device_item)
            sensor_item.setText(0, sensor_display_name)
            sensor_item.setData(0, Qt.ItemDataRole.UserRole, sensor_data)
            self.update_sensor_item(sensor_item, sensor_data)
        return device_item

    @Slot(dict,bool)
    def update_tree_and_db(self,data,from_db=False):
        device_id=data['deviceId']
        if not from_db: data['last_seen']=int(time.time())
        if not from_db and 'deviceName' in data: update_device_display_name(device_id, data['deviceName'])
            
        if device_id not in self.device_items:
            self._create_device_item(data)
        else:
            device_item=self.device_items[device_id]
            device_item.setIcon(0,self.icons['online'])
            device_item.setText(0,f"{get_device_display_name(device_id)}")
            old_data = device_item.data(0, Qt.ItemDataRole.UserRole)
            if old_data: old_data.update(data); device_item.setData(0, Qt.ItemDataRole.UserRole, old_data)
            else: device_item.setData(0, Qt.ItemDataRole.UserRole, data)
            
            child_sensors_map={item.data(0,Qt.ItemDataRole.UserRole)['id']:item for item in[device_item.child(i)for i in range(device_item.childCount())]}
            for new_sensor_data in data['sensors']:
                if new_sensor_data.get('id') in child_sensors_map:
                    self.update_sensor_item(child_sensors_map[new_sensor_data['id']], new_sensor_data)
        if not from_db: process_incoming_data(data)
    
    # --- Alarms ---
    def load_and_display_alarm_rules(self):
        self.ui.alarmsTableWidget.setRowCount(0); self.alarm_rules=get_all_alarm_rules()
        action_map={"notification":"Уведомление","logfile":"Запись в лог"}
        for rule in self.alarm_rules:
            row_pos=self.ui.alarmsTableWidget.rowCount(); self.ui.alarmsTableWidget.insertRow(row_pos)
            target_device="Любое"if rule['target_device_id']=='any'else get_device_display_name(rule['target_device_id'])
            action_text=action_map.get(rule.get('action_type','notification'),"Неизвестно")
            self.ui.alarmsTableWidget.setItem(row_pos,0,QTableWidgetItem(f"{target_device} / {rule['target_sensor_name']}"))
            self.ui.alarmsTableWidget.setItem(row_pos,1,QTableWidgetItem(rule['data_key']))
            self.ui.alarmsTableWidget.setItem(row_pos,2,QTableWidgetItem(rule['condition']))
            self.ui.alarmsTableWidget.setItem(row_pos,3,QTableWidgetItem(str(rule['value'])))
            self.ui.alarmsTableWidget.setItem(row_pos,4,QTableWidgetItem(action_text))
            self.ui.alarmsTableWidget.item(row_pos,0).setData(Qt.ItemDataRole.UserRole,rule['id'])
    
    def on_add_alarm(self):
        self.log("Открытие диалога добавления правила..."); dialog=AlarmDialog(devices=list(self.device_items.keys()),parent=self)
        if dialog.exec():
            data=dialog.get_data(); self.log(f"Добавление нового правила: {data}")
            add_alarm_rule(target_device=data['target_device'],target_sensor='any',data_key=data['data_key'],condition=data['condition'],value=data['value'],action_type=data['action_type'])
            self.load_and_display_alarm_rules()
    
    def on_remove_alarm(self):
        selected_rows=self.ui.alarmsTableWidget.selectionModel().selectedRows()
        if not selected_rows: QMessageBox.warning(self,"Ошибка","Пожалуйста, выберите правило для удаления."); return
        rule_item=self.ui.alarmsTableWidget.item(selected_rows[0].row(),0); rule_id=rule_item.data(Qt.ItemDataRole.UserRole)
        reply=QMessageBox.question(self,"Подтверждение",f"Вы уверены, что хотите удалить правило ID {rule_id}?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if reply==QMessageBox.StandardButton.Yes: remove_alarm_rule(rule_id); self.load_and_display_alarm_rules(); self.log(f"Правило ID {rule_id} удалено.")
    
    def check_alarms(self,data):
        for sensor in data['sensors']:
            for data_key,value in sensor['data'].items():
                for rule in self.alarm_rules:
                    device_match=rule['target_device_id']=='any' or rule['target_device_id']==data['deviceId']
                    sensor_match=rule['target_sensor_name']=='any'or rule['target_sensor_name']==(get_sensor_display_name(data['deviceId'],sensor['id'])or sensor['name'])
                    if device_match and sensor_match and rule['data_key']==data_key:
                        try:
                            if (rule['condition']=='>' and float(value)>rule['value']) or \
                               (rule['condition']=='<' and float(value)<rule['value']):
                                title=f"ALARM: {get_sensor_display_name(data['deviceId'],sensor['id']) or sensor['name']} на {get_device_display_name(data['deviceId'])}"
                                message=f"{data_key} = {value} (условие: {rule['condition']} {rule['value']})"
                                self.log(f"СРАБОТАЛ АЛАРМ! {title} - {message}")
                                if rule.get('action_type','notification')=='notification': self.notification_request.emit(title,message)
                                else: log_alarm_to_file(f"СРАБОТАЛ АЛАРМ! {title} - {message}")
                        except (ValueError,TypeError): continue
    
    # --- UI Slots and Display Logic ---
    @Slot(str,str)
    def show_notification(self,title,message): Notification(title=title,description=message,duration=5,urgency=Notification.URGENCY_CRITICAL).send()
    
    @Slot()
    def check_device_statuses(self):
        current_time=int(time.time())
        for device_id,device_item in self.device_items.items():
            device_data = device_item.data(0, Qt.ItemDataRole.UserRole)
            is_currently_online = (current_time - device_data.get('last_seen', 0)) <= OFFLINE_THRESHOLD_S
            if is_currently_online != device_data.get('is_online', True):
                device_data['is_online'] = is_currently_online
                self.log(f"Устройство {device_id} {'снова онлайн' if is_currently_online else 'ушло в оффлайн'}.")
                device_item.setIcon(0, self.icons['online' if is_currently_online else 'offline'])
                if self.currently_selected_item == device_item: self.on_tree_item_clicked(device_item, 0)
    
    # ИСПРАВЛЕНИЕ: Восстановлен метод
    @Slot(QTreeWidgetItem,int)
    def on_tree_item_double_clicked(self,item,column):
        is_device=item.parent() is None
        if is_device:
            device_id=item.data(0,Qt.ItemDataRole.UserRole)['deviceId']
            current_name=get_device_display_name(device_id)
        else:
            sensor_info=item.data(0,Qt.ItemDataRole.UserRole)
            device_id=item.parent().data(0,Qt.ItemDataRole.UserRole)['deviceId']
            sensor_id=sensor_info['id']
            current_name=get_sensor_display_name(device_id,sensor_id) or sensor_info['name']
            
        new_name,ok=QInputDialog.getText(self,"Переименовать","Введите новое имя:",text=current_name)
        if ok and new_name and new_name!=current_name:
            if is_device:
                update_device_display_name(device_id,new_name)
                item.setText(0,f"{new_name}")
                self.log(f"Устройство {device_id} переименовано в '{new_name}'")
            else:
                update_sensor_display_name(device_id,sensor_id,new_name)
                item.setText(0,new_name)
                self.log(f"Сенсор {sensor_id} на {device_id} переименован в '{new_name}'")

    def _get_selected_item_info(self, item):
        if item.parent() is None: # Это устройство
            device_info = item.data(0, Qt.ItemDataRole.UserRole)
            series_to_plot = []
            for i in range(item.childCount()):
                series = self.prepare_series_data(device_info, item.child(i).data(0, Qt.ItemDataRole.UserRole))
                if series: series_to_plot.append(series)
            title = f"Все температуры: {get_device_display_name(device_info.get('deviceId'))}"
            return {'device_id': device_info.get('deviceId'), 'card_info': device_info, 'series': series_to_plot, 'title': title}
        else: # Это сенсор
            device_info = item.parent().data(0, Qt.ItemDataRole.UserRole)
            sensor_info = item.data(0, Qt.ItemDataRole.UserRole)
            series = self.prepare_series_data(device_info, sensor_info)
            title = f"История показаний: {item.text(0)}"
            return {'device_id': device_info.get('deviceId'), 'card_info': device_info, 'series': [series] if series else [], 'title': title}

    @Slot(QTreeWidgetItem, int)
    def on_tree_item_clicked(self, item, column):
        self.currently_selected_item = item
        info = self._get_selected_item_info(item)
        
        if not info.get('device_id'): return

        self.clear_live_cards()
        self.ui.timeScrollBar.setEnabled(False)
        self.ui.plotWidget.clear()
        
        self.update_live_cards(info['card_info'], info['series'])
        
        if not info['series']: self.log("Нет данных для построения."); return
            
        plotted_names = [s['name'] for s in info['series']]
        alarm_lines = [{'value': r['value'], 'condition': r['condition']} for r in self.alarm_rules if (r['target_device_id'] == 'any' or r['target_device_id'] == info['device_id']) and (r['target_sensor_name'] == 'any' or r['target_sensor_name'] in plotted_names) and 'temperature' in r['data_key']]
        
        total_points = self.ui.plotWidget.plot_multiple(info['series'], info['title'], alarm_lines)
        
        self.ui.timeScrollBar.blockSignals(True) 
        if total_points > GRAPH_WINDOW_SIZE:
            self.ui.timeScrollBar.setEnabled(True)
            self.ui.timeScrollBar.setRange(0, total_points - GRAPH_WINDOW_SIZE)
            self.ui.timeScrollBar.setPageStep(GRAPH_WINDOW_SIZE // 4)
            self.ui.timeScrollBar.setValue(total_points - GRAPH_WINDOW_SIZE)
        else: self.ui.timeScrollBar.setRange(0, 0)
        self.ui.timeScrollBar.blockSignals(False)
        self.on_time_scroll(self.ui.timeScrollBar.value())

    @Slot(int)
    def on_time_scroll(self, value):
        if not self.ui.plotWidget.full_series_data or not any(s.get('x') for s in self.ui.plotWidget.full_series_data): return
        total_points = max(len(s['x']) for s in self.ui.plotWidget.full_series_data if s.get('x'))
        window_size = min(GRAPH_WINDOW_SIZE, total_points)
        self.ui.plotWidget.set_time_view(value, window_size)

    def clear_live_cards(self):
        while self.ui.cardsLayout.count():
            item = self.ui.cardsLayout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
    
    def _create_status_card(self, device_info):
        card = QGroupBox(device_info.get('deviceName', 'Статус устройства'))
        card.setStyleSheet(self.card_style + self.status_card_title_style)
        layout = QFormLayout(card)
        layout.setContentsMargins(8, 20, 8, 8); layout.setVerticalSpacing(4)
        status = device_info.get('status', {}); network_map = {'ethernet': 'Ethernet', 'wifi': 'Wi-Fi', 'ap': 'Точка доступа'}
        alarm_label = QLabel("ДА" if status.get('alarm_active', False) else "НЕТ")
        alarm_label.setStyleSheet(f"color: {'#E74C3C' if status.get('alarm_active', False) else '#2ECC71'}; font-weight: bold;")
        
        layout.addRow("IP Адрес:", QLabel(status.get('ip_address', 'N/A')))
        layout.addRow("Uptime:", QLabel(format_uptime(device_info.get('uptime_ms'))))
        layout.addRow("Подключение:", QLabel(network_map.get(status.get('network'), 'N/A')))
        layout.addRow("Тревога:", alarm_label)
        if device_info.get('geo', {}).get('lat'): layout.addRow("Координаты:", QLabel(f"{device_info['geo']['lat']:.4f}, {device_info['geo']['lon']:.4f}"))
        sensor_ids = ", ".join([str(s.get('id', '?')) for s in device_info.get('sensors', [])])
        layout.addRow("Сенсоры:", QLabel(f"{len(device_info.get('sensors', []))} (ID: {sensor_ids})"))
        
        card.setMinimumWidth(220)
        return card

    def _create_sensor_card(self, series_data):
        card = QGroupBox(series_data['name'])
        card.setStyleSheet(self.card_style + self.sensor_card_title_style)
        layout = QVBoxLayout(card); layout.setContentsMargins(8, 20, 8, 8)
        value = series_data['y'][-1] if series_data.get('y') else 'N/A'
        
        value_layout = QHBoxLayout(); value_layout.addStretch()
        value_label = QLabel(); unit_label = QLabel()
        
        if isinstance(value, (int, float)): value_label.setText(f"{value:.2f}"); unit_label.setText("°C")
        else: value_label.setText("N/A"); unit_label.setText("")
        
        font_value = value_label.font(); font_value.setPointSize(40); font_value.setBold(True)
        value_label.setFont(font_value); value_label.setStyleSheet("color: #5DADE2; padding-bottom: 5px;") 
        
        font_unit = unit_label.font(); font_unit.setPointSize(18)
        unit_label.setFont(font_unit); unit_label.setStyleSheet("color: #AAAAAA; margin-top: 10px; margin-left: -5px;")
        
        value_layout.addWidget(value_label); value_layout.addWidget(unit_label)
        value_layout.addStretch(); layout.addLayout(value_layout)
        
        card.setMinimumWidth(120); card.adjustSize()
        return card

    def update_live_cards(self, device_info, series_data):
        self.clear_live_cards()
        if device_info: self.ui.cardsLayout.addWidget(self._create_status_card(device_info))
        for series in series_data: self.ui.cardsLayout.addWidget(self._create_sensor_card(series))
        self.ui.cardsLayout.invalidate(); self.ui.cardsPanel.layout().activate()

    def prepare_series_data(self, device_info, sensor_info):
        if not sensor_info or not device_info: return None
        device_id = device_info.get('deviceId'); sensor_id = sensor_info.get('id')
        readings = get_readings_for_sensor(device_id, sensor_id)
        if not readings: return None
        data_key = next((k for k in readings[0][1] if 'temperature' in k), None)
        if not data_key: return None
        timestamps = []; values = []
        for ts, data_dict in readings:
            if data_dict and data_key in data_dict:
                try: timestamps.append(datetime.fromtimestamp(ts)); values.append(float(data_dict[data_key]))
                except (ValueError, TypeError, KeyError): continue
        if not timestamps: return None
        return {'name': get_sensor_display_name(device_id, sensor_id) or sensor_info.get('name', 'N/A'), 'x': timestamps, 'y': values}

    def update_sensor_item(self, sensor_item, sensor_data):
        if not sensor_data.get('data'): return
        parent_device_id = sensor_item.parent().data(0, Qt.ItemDataRole.UserRole)['deviceId']
        display_name = get_sensor_display_name(parent_device_id, sensor_data['id']) or sensor_data['name']
        sensor_item.setText(0, display_name)
        first_key = next(iter(sensor_data['data']), None)
        if first_key and 'temperature' in first_key: sensor_item.setIcon(0, self.icons['temp'])
        elif first_key and 'humidity' in first_key: sensor_item.setIcon(0, self.icons['humidity'])

    @Slot(str)
    def log(self, message): print(f"[{time.strftime('%H:%M:%S')}] {message}")