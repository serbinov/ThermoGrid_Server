# file: device_delegate.py
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem
from PySide6.QtGui import QColor, QBrush, QPen, QPalette
from PySide6.QtCore import Qt, QSize, QRect

class DeviceDelegate(QStyledItemDelegate):
    def __init__(self, tree_widget):
        super().__init__(tree_widget)
        self.tree_widget = tree_widget
        self.device_bg_color = QColor("#2A82DA")
        self.device_text_color = QColor("#FFFFFF")
        self.border_color = QColor("#4F627B")

    def paint(self, painter, option, index):
        if not index.parent().isValid():
            painter.save()
            bg_rect = self.get_group_rect(index)
            bg_brush = QBrush(self.device_bg_color)
            
            painter.setRenderHint(painter.RenderHint.Antialiasing)
            painter.setPen(QPen(self.border_color, 1))
            painter.setBrush(bg_brush)
            painter.drawRoundedRect(bg_rect, 5, 5)

            header_rect = option.rect.adjusted(2, 2, -2, -2)
            
            icon_rect = QRect(header_rect.left() + 5, header_rect.top() + (header_rect.height() - 16) // 2, 16, 16)
            icon = index.data(Qt.ItemDataRole.DecorationRole)
            if icon: icon.paint(painter, icon_rect)

            text_rect = header_rect.adjusted(26, 0, 0, 0) 
            painter.setPen(self.device_text_color)
            text = index.data(Qt.ItemDataRole.DisplayRole)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)

            painter.restore()
        else:
            new_option = QStyleOptionViewItem(option)
            # Устанавливаем цвет выделения для сенсоров
            if option.state & QStyle.State_Selected:
                 new_option.palette.setColor(QPalette.ColorRole.Highlight, QColor("#4A5568"))
                 new_option.palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))

            new_option.palette.setColor(QPalette.ColorRole.AlternateBase, Qt.GlobalColor.transparent)
            new_option.palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.transparent)
            super().paint(painter, new_option, index)

    def get_group_rect(self, index):
        if not index.isValid() or index.parent().isValid():
            return QRect()
        
        start_rect = self.tree_widget.visualRect(index)
        
        if not index.model().hasChildren(index) or not self.tree_widget.isExpanded(index):
            return start_rect.adjusted(2, 2, -2, -2)
        
        # ИСПРАВЛЕНИЕ: Вызываем .child() у модели, а не у индекса
        last_child_index = index.model().index(index.model().rowCount(index) - 1, 0, index)
        end_rect = self.tree_widget.visualRect(last_child_index)
        
        return start_rect.united(end_rect).adjusted(2, 2, -2, -2)

    def sizeHint(self, option, index):
        if not index.parent().isValid():
            return QSize(super().sizeHint(option, index).width(), 30)
        return QSize(super().sizeHint(option, index).width(), 24)