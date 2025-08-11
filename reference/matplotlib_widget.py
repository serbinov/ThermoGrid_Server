# file: matplotlib_widget.py
from PySide6 import QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from matplotlib.ticker import MultipleLocator
import matplotlib.pyplot as plt
from datetime import datetime, time, timedelta
import numpy as np
import math

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None):
        self.fig = Figure(dpi=100) 
        self.axes = self.fig.add_subplot(111)
        self.fig.patch.set_facecolor('#19232D')
        self.axes.set_facecolor('#19232D')
        self.fig.subplots_adjust(left=0.1, right=0.95, top=0.9, bottom=0.2)
        super(MplCanvas, self).__init__(self.fig)
        self.setParent(parent)

class MatplotlibWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(MatplotlibWidget, self).__init__(parent)
        self.canvas = MplCanvas(self)
        layout = QtWidgets.QVBoxLayout(); layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.canvas); self.setLayout(layout)
        
        self.legend = None; self.plotted_lines = {}; self.annot = None
        self.crosshair_v = self.canvas.axes.axvline(x=0, color='gray', linestyle='--', linewidth=0.7, visible=False)
        self.crosshair_h = self.canvas.axes.axhline(y=0, color='gray', linestyle='--', linewidth=0.7, visible=False)
        self.full_series_data = []
        self.last_start_index = 0
        self.last_window_size = 0
        
        self.pick_connection_id = None
        self.canvas.mpl_connect("motion_notify_event", self.hover)

    def plot_multiple(self, series_data, title, alarm_lines=None):
        ax = self.canvas.axes; ax.cla()
        self.plotted_lines.clear()
        
        self.full_series_data = series_data

        self.crosshair_v = ax.axvline(x=0, color='gray', linestyle='--', linewidth=0.7, visible=False)
        self.crosshair_h = ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.7, visible=False)
        self.annot = ax.annotate("", xy=(0,0), xytext=(-20,20), textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="yellow", ec="black", lw=1),
                            arrowprops=dict(arrowstyle="->"), color="black", zorder=10)
        self.annot.set_visible(False)

        all_x, all_y = [], []; total_points = 0
        for series in series_data:
            # ИСПРАВЛЕНИЕ: Проверяем, что есть данные для отрисовки
            if series.get('x') and series.get('y'):
                line, = ax.plot(series['x'], series['y'], marker='o', linestyle='-', label=series['name'], markersize=4)
                self.plotted_lines[series['name']] = line
                all_x.extend(series['x']); all_y.extend(series['y'])
                if len(series['x']) > total_points: total_points = len(series['x'])

        if not all_x: self.clear(); return 0

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.grid(True, linestyle='--', alpha=0.4, color='gray')
        ax.yaxis.set_major_locator(MultipleLocator(1))

        if alarm_lines:
            for alarm in alarm_lines:
                ax.axhline(y=alarm['value'], color='red', linestyle='--', linewidth=1.2, label=f"Alarm {alarm['condition']} {alarm['value']}")

        min_date, max_date = min(all_x).date(), max(all_x).date()
        current_date = min_date + timedelta(days=1)
        while current_date <= max_date:
            midnight = datetime.combine(current_date, time.min)
            ax.axvline(midnight, color='white', linestyle=':', linewidth=0.8, alpha=0.5)
            current_date += timedelta(days=1)
        
        start_date_str = min(all_x).strftime('%d.%m.%Y')
        full_title = f"{title}\n(Всего точек: {total_points}, с {start_date_str})"
        ax.set_title(full_title, color='white', fontsize=12)

        ax.set_xlabel('Время', color='gray'); ax.set_ylabel('Температура, °C', color='gray')
        ax.tick_params(axis='x', colors='white', rotation=0); ax.tick_params(axis='y', colors='white')
        ax.spines['bottom'].set_color('gray'); ax.spines['top'].set_color('gray') 
        ax.spines['right'].set_color('gray'); ax.spines['left'].set_color('gray')

        self.draw_statistics(ax, all_x, all_y)

        if self.plotted_lines:
            self.legend = ax.legend(loc='upper left', facecolor='#19232D', edgecolor='gray', fontsize='small')
            for legline, legtext in zip(self.legend.get_lines(), self.legend.get_texts()):
                original_label = legtext.get_text()
                if original_label.startswith("Alarm"): continue
                legtext.set_text(f"☑ {original_label}")
                legline.set_picker(5); legline.set_gid(original_label)
            
            for legtext in self.legend.get_texts(): legtext.set_color('white')
            
            # ИСПРАВЛЕНИЕ: Правильно переподключаем обработчик событий
            if self.pick_connection_id:
                 self.canvas.mpl_disconnect(self.pick_connection_id)
            self.pick_connection_id = self.canvas.mpl_connect('pick_event', self.on_pick)
        
        self.canvas.draw()
        return total_points

    def draw_statistics(self, ax, all_x, all_y):
        stats_text = ""
        if all_y:
            stats_text += "Всё время:\n  Min: {:.1f}°C, Max: {:.1f}°C, Avg: {:.1f}°C\n".format(
                np.min(all_y), np.max(all_y), np.mean(all_y))
        now = datetime.now()
        last_24h_y = [y for x, y in zip(all_x, all_y) if x > (now - timedelta(hours=24))]
        if last_24h_y:
            stats_text += "Последние 24ч:\n  Min: {:.1f}°C, Max: {:.1f}°C, Avg: {:.1f}°C".format(
                np.min(last_24h_y), np.max(last_24h_y), np.mean(last_24h_y))
        else:
            stats_text += "Последние 24ч: нет данных"
        ax.text(0.99, 0.98, stats_text, transform=ax.transAxes, fontsize=8,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='#606060', alpha=0.6),
                color='white')
    
    def set_time_view(self, start_index, window_size):
        if not self.full_series_data: return
        self.last_start_index = start_index
        self.last_window_size = window_size

        ax = self.canvas.axes
        longest_x_series = max((s['x'] for s in self.full_series_data if s.get('x')), key=len, default=[])
        if not longest_x_series: return

        # ИСПРАВЛЕНИЕ: Корректно обрезаем индексы
        start_index = max(0, int(start_index))
        end_index = min(start_index + int(window_size), len(longest_x_series))
        
        if start_index >= end_index: return

        start_time = longest_x_series[start_index]
        end_time = longest_x_series[end_index-1]
        
        start_time_num = mdates.date2num(start_time)
        end_time_num = mdates.date2num(end_time)
        
        # Чтобы избежать пустого графика при одинаковых временах
        if start_time_num == end_time_num:
            end_time_num += 1/24/60 # Добавляем одну минуту

        ax.set_xlim(start_time_num, end_time_num)

        visible_y_values = []
        for series in self.full_series_data:
            line = self.plotted_lines.get(series['name'])
            if not line or not line.get_visible() or not series.get('x'): continue
            x_data_num = mdates.date2num(series['x'])
            y_data_np = np.array(series['y'])
            indices = np.where((x_data_num >= start_time_num) & (x_data_num <= end_time_num))
            if indices[0].size > 0: visible_y_values.extend(y_data_np[indices])
            
        if not visible_y_values:
            ax.relim(); ax.autoscale_view(True, scalex=False) # Не масштабируем X, т.к. мы его задали
        else:
            min_y = min(visible_y_values)
            max_y = max(visible_y_values)
            data_range = max_y - min_y
            if data_range < 2.0: data_range = 2.0
            
            bottom_margin = data_range * 0.15 
            top_margin = data_range * 0.40
            
            # Округляем до целых вверх и вниз, чтобы получить хороший вид
            final_bottom = math.floor(min_y - bottom_margin)
            final_top = math.ceil(max_y + top_margin)

            # Проверяем, чтобы разница была хотя бы 2 градуса
            if final_top - final_bottom < 2:
                final_top = final_bottom + 2

            ax.set_ylim(final_bottom, final_top)

        self.canvas.draw_idle()

    def update_annot(self, line, ind):
        pos = line.get_xydata()[ind["ind"][0]]
        self.annot.xy = pos
        timestamp_str = mdates.num2date(pos[0]).strftime('%d.%m %H:%M:%S')
        text = f"{line.get_label()}\nВремя: {timestamp_str}\nЗначение: {pos[1]:.2f}°C"
        self.annot.set_text(text)
        self.annot.get_bbox_patch().set_alpha(0.8)

    def hover(self, event):
        if not self.annot: return
        vis = self.annot.get_visible()
        if event.inaxes == self.canvas.axes:
            self.crosshair_v.set_xdata([event.xdata, event.xdata]); self.crosshair_v.set_visible(True)
            self.crosshair_h.set_ydata([event.ydata, event.ydata]); self.crosshair_h.set_visible(True)
            found = False
            for line in self.canvas.axes.get_lines():
                if not line.get_visible() or not hasattr(line, 'get_label') or line.get_label().startswith('_') or line.get_label().startswith('Alarm'): continue
                cont, ind = line.contains(event)
                if cont:
                    self.update_annot(line, ind); self.annot.set_visible(True)
                    found = True; break
            if not found and vis: self.annot.set_visible(False)
            self.canvas.draw_idle()
        elif vis or self.crosshair_v.get_visible():
            self.annot.set_visible(False); self.crosshair_v.set_visible(False); self.crosshair_h.set_visible(False)
            self.canvas.draw_idle()

    def on_pick(self, event):
        label = event.artist.get_gid()
        if label in self.plotted_lines:
            line = self.plotted_lines[label]; visible = not line.get_visible()
            line.set_visible(visible)
            if not visible and self.annot and self.annot.get_visible():
                if self.annot.get_text().split('\n')[0] == label: self.annot.set_visible(False)
            
            # Обновляем легенду
            if self.legend:
                for legline, legtext in zip(self.legend.get_lines(), self.legend.get_texts()):
                    if legline.get_gid() == label:
                        text_label = legtext.get_text().replace('☑ ', '').replace('☐ ', '')
                        new_text = f"☑ {text_label}" if visible else f"☐ {text_label}"
                        legtext.set_text(new_text); legtext.set_alpha(1.0 if visible else 0.5); legline.set_alpha(1.0 if visible else 0.5)
            
            # ИСПРАВЛЕНИЕ: Перерисовываем с текущими параметрами, чтобы обновить масштаб
            self.set_time_view(self.last_start_index, self.last_window_size)
            self.canvas.draw()

    def clear(self):
        ax = self.canvas.axes; ax.cla()
        ax.set_title("Выберите устройство или сенсор", color='white')
        if self.annot: self.annot.set_visible(False)
        if hasattr(self, 'crosshair_v'): self.crosshair_v.set_visible(False); self.crosshair_h.set_visible(False)
        self.canvas.draw()