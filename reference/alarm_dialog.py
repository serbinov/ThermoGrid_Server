# file: alarm_dialog.py
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QVBoxLayout, QFormLayout, 
    QComboBox, QLineEdit, QLabel, QDoubleSpinBox
)

class AlarmDialog(QDialog):
    def __init__(self, devices, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить правило оповещения")

        # --- Элементы управления ---
        self.targetDevice = QComboBox()
        self.targetDevice.addItem("Любое устройство", "any") 
        for device_id in devices:
            self.targetDevice.addItem(device_id, device_id)
            
        self.dataKey = QComboBox()
        self.dataKey.addItems(["temperature_c", "humidity_percent", "pressure_hpa"])
        self.dataKey.setEditable(True)

        self.condition = QComboBox()
        self.condition.addItems([">", "<"])

        self.value = QDoubleSpinBox()
        self.value.setRange(-10000, 10000)
        self.value.setDecimals(2)
        
        # НОВЫЙ ЭЛЕМЕНТ: Выбор типа оповещения
        self.actionType = QComboBox()
        self.actionType.addItem("Системное уведомление", "notification")
        self.actionType.addItem("Запись в лог-файл", "logfile")

        # --- Кнопки OK и Cancel ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        # --- Компоновка ---
        form_layout = QFormLayout()
        form_layout.addRow("Целевое устройство:", self.targetDevice)
        form_layout.addRow("Тип данных (ключ):", self.dataKey)
        form_layout.addRow("Условие:", self.condition)
        form_layout.addRow("Пороговое значение:", self.value)
        form_layout.addRow("Тип оповещения:", self.actionType) # Добавляем в форму

        main_layout = QVBoxLayout()
        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
    
    def get_data(self):
        """Возвращает данные из формы в виде словаря."""
        return {
            'target_device': self.targetDevice.currentData(),
            'data_key': self.dataKey.currentText(),
            'condition': self.condition.currentText(),
            'value': self.value.value(),
            'action_type': self.actionType.currentData() # Возвращаем ID действия
        }