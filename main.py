import calendar
import json
import math
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

DATA_DIR = APP_DIR / "data"
EVENTS_FILE = DATA_DIR / "events.json"
VENDOR_DIR = APP_DIR / ".vendor"

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

try:
    from PySide6.QtCore import QRectF, QSize, Qt, QTimer
    from PySide6.QtGui import QColor, QFont, QPainter, QPen
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QFrame,
        QGraphicsDropShadowEffect,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as error:
    if error.name and error.name.startswith("PySide6"):
        print("缺少 PySide6。请在 VSCode 终端里运行：")
        print("python -m pip install PySide6")
        print("如果想只安装到这个项目里，运行：")
        print("python -m pip install PySide6 --target .vendor")
        sys.exit(1)
    raise

COLORS = {
    "蓝色": "#3B82F6",
    "绿色": "#22C55E",
    "橙色": "#F59E0B",
    "红色": "#EF4444",
    "紫色": "#8B5CF6",
}


class EventStore:
    def __init__(self, path):
        self.path = path
        self.events = []
        self.load()

    def load(self):
        DATA_DIR.mkdir(exist_ok=True)
        if not self.path.exists():
            self.events = []
            self.save()
            return

        try:
            with self.path.open("r", encoding="utf-8") as file:
                self.events = json.load(file)
        except (json.JSONDecodeError, OSError):
            self.events = []

    def save(self):
        DATA_DIR.mkdir(exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(self.events, file, ensure_ascii=False, indent=2)

    def events_for_day(self, day):
        key = day.isoformat()
        day_events = [event for event in self.events if event["date"] == key]
        return sorted(day_events, key=lambda item: (item["start_hour"], item["title"]))

    def events_between(self, start_day, end_day):
        start_key = start_day.isoformat()
        end_key = end_day.isoformat()
        range_events = [event for event in self.events if start_key <= event["date"] <= end_key]
        return sorted(range_events, key=lambda item: (item["date"], item["start_hour"], item["title"]))

    def add(self, event):
        event["id"] = str(uuid.uuid4())
        self.events.append(event)
        self.save()

    def update(self, event_id, new_event):
        for index, event in enumerate(self.events):
            if event["id"] == event_id:
                new_event["id"] = event_id
                self.events[index] = new_event
                self.save()
                return

    def delete(self, event_id):
        self.events = [event for event in self.events if event["id"] != event_id]
        self.save()


class Card(QFrame):
    def __init__(self, parent=None, shadow=False):
        super().__init__(parent)
        self.setObjectName("card")
        if shadow:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(22)
            effect.setColor(QColor(15, 23, 42, 24))
            effect.setOffset(0, 8)
            self.setGraphicsEffect(effect)


class TimeWheel(QListWidget):
    item_height = 34

    def __init__(self, start_hour, end_hour, selected_hour, parent=None):
        super().__init__(parent)
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.setObjectName("timeWheel")
        self.setFixedHeight(128)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSpacing(4)
        self.setUniformItemSizes(True)

        for hour in range(start_hour, end_hour + 1):
            item = QListWidgetItem(f"{hour:02d}:00")
            item.setData(Qt.UserRole, hour)
            item.setTextAlignment(Qt.AlignCenter)
            item.setSizeHint(QSize(120, self.item_height))
            self.addItem(item)

        self.set_hour(selected_hour)

    def hour(self):
        item = self.currentItem()
        if item is None:
            return self.start_hour
        return item.data(Qt.UserRole)

    def set_hour(self, hour):
        hour = max(self.start_hour, min(self.end_hour, hour))
        row = hour - self.start_hour
        self.setCurrentRow(row)
        self.scrollToItem(self.item(row), QListWidget.PositionAtCenter)
        self.viewport().update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_hour(self.hour() - 1)
        elif delta < 0:
            self.set_hour(self.hour() + 1)
        event.accept()


class EventDialog(QDialog):
    def __init__(self, parent, selected_date, hour, on_save, event=None, end_hour=None, on_delete=None):
        super().__init__(parent)
        self.selected_date = selected_date
        self.on_save = on_save
        self.on_delete = on_delete
        self.event_data = event

        self.setModal(True)
        self.setWindowTitle("编辑日程" if event else "添加日程")
        self.setMinimumSize(560, 680)
        self.resize(600, 720)
        self.setObjectName("eventDialog")

        self.title_input = QLineEdit(event.get("title", "") if event else "")
        self.title_input.setPlaceholderText("例如：英语课、写作业、运动")

        start_hour = event.get("start_hour", hour) if event else hour
        initial_end_hour = min(24, start_hour + event.get("duration", 1)) if event else (end_hour or min(24, start_hour + 1))
        self.start_input = TimeWheel(0, 23, start_hour)
        self.end_input = TimeWheel(1, 24, initial_end_hour)
        self.start_input.currentRowChanged.connect(self.keep_end_after_start)
        self.end_input.currentRowChanged.connect(self.keep_end_after_start)

        current_color = event.get("color_name", "蓝色") if event else "蓝色"
        self.selected_color_name = current_color if current_color in COLORS else "蓝色"
        self.color_buttons = {}

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("备注，可不填")
        if event:
            self.notes_input.setPlainText(event.get("notes", ""))

        self.build()

    def build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 18)
        root.setSpacing(12)

        title = QLabel("日程信息")
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        title_card = self.section_card("内容")
        title_card.layout().addWidget(self.title_input)
        root.addWidget(title_card)

        time_card = self.section_card("时间")
        time_row = QHBoxLayout()
        time_row.setSpacing(12)
        time_row.addWidget(self.field("开始时间", self.start_input))
        time_row.addWidget(self.field("结束时间", self.end_input))
        time_card.layout().addLayout(time_row)
        root.addWidget(time_card)

        color_card = self.section_card("颜色")
        color_row = QHBoxLayout()
        color_row.setSpacing(12)
        color_row.setContentsMargins(0, 2, 0, 0)

        for name, value in COLORS.items():
            button = QPushButton()
            button.setFixedSize(34, 34)
            button.setCursor(Qt.PointingHandCursor)
            button.setObjectName("colorSwatch")
            button.setProperty("colorName", name)
            button.clicked.connect(lambda checked=False, item_name=name: self.select_color(item_name))
            self.color_buttons[name] = button
            color_row.addWidget(button)

        color_row.addStretch()
        color_card.layout().addLayout(color_row)
        root.addWidget(color_card)
        self.refresh_color_buttons()

        notes_card = self.section_card("备注")
        notes_card.layout().addWidget(self.notes_input)
        root.addWidget(notes_card, stretch=1)

        actions = QHBoxLayout()
        actions.addStretch()

        cancel = QPushButton("取消")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)

        done = QPushButton("完成")
        done.setObjectName("primaryButton")
        done.clicked.connect(self.save)

        if self.event_data and self.on_delete:
            delete = QPushButton("删除")
            delete.setObjectName("dialogDeleteButton")
            delete.clicked.connect(self.delete_current_event)
            actions.addWidget(delete)

        actions.addWidget(cancel)
        actions.addWidget(done)
        root.addLayout(actions)

        self.title_input.setFocus()

    def section_card(self, title_text):
        card = Card()
        card.setObjectName("dialogSection")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        label = QLabel(title_text)
        label.setObjectName("sectionLabel")
        layout.addWidget(label)
        return card

    def field(self, label_text, widget):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(widget)
        return box

    def select_color(self, color_name):
        self.selected_color_name = color_name
        self.refresh_color_buttons()

    def refresh_color_buttons(self):
        for name, button in self.color_buttons.items():
            selected = name == self.selected_color_name
            border = "#2563EB" if selected else "#FFFFFF"
            width = "3px" if selected else "2px"
            button.setStyleSheet(
                f"""
                QPushButton {{
                    background: {COLORS[name]};
                    border: {width} solid {border};
                    border-radius: 9px;
                }}
                QPushButton:hover {{
                    border: 3px solid #BFDBFE;
                }}
                """
            )

    def keep_end_after_start(self):
        start_hour = self.start_input.hour()
        end_hour = self.end_input.hour()
        if end_hour <= start_hour:
            self.end_input.set_hour(min(24, start_hour + 1))

    def delete_current_event(self):
        if not self.event_data or not self.on_delete:
            return

        deleted = self.on_delete(self.event_data)
        if deleted:
            self.accept()

    def save(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "还缺一点", "请先输入日程标题。")
            return

        start_hour = self.start_input.hour()
        end_hour = self.end_input.hour()
        if end_hour <= start_hour:
            QMessageBox.warning(self, "时间不对", "结束时间必须晚于开始时间。")
            return

        duration = end_hour - start_hour
        color_name = self.selected_color_name

        event = {
            "date": self.selected_date.isoformat(),
            "title": title,
            "start_hour": start_hour,
            "duration": duration,
            "color_name": color_name,
            "color": COLORS[color_name],
            "notes": self.notes_input.toPlainText().strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.on_save(event, self.event_data["id"] if self.event_data else None)
        self.accept()


def rgba_from_hex(hex_color, alpha):
    clean = hex_color.lstrip("#")
    red = int(clean[0:2], 16)
    green = int(clean[2:4], 16)
    blue = int(clean[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


class TimelineEventBlock(QFrame):
    def __init__(self, event, on_edit, on_delete, parent=None):
        super().__init__(parent)
        self.event_data = event
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.setObjectName("timelineEventBlock")
        self.setCursor(Qt.PointingHandCursor)

        color = event.get("color", "#3B82F6")
        self.setStyleSheet(
            f"""
            #timelineEventBlock {{
                background: {rgba_from_hex(color, 30)};
                border: 1px solid {rgba_from_hex(color, 95)};
                border-left: 5px solid {color};
                border-radius: 10px;
            }}
            """
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(9, 4, 6, 4)
        root.setSpacing(6)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(1)

        title = QLabel(event["title"])
        title.setObjectName("timelineEventTitle")
        title.setWordWrap(False)
        info.addWidget(title)

        root.addLayout(info, stretch=1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_edit(self.event_data)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.on_edit(self.event_data)
        event.accept()
        super().mouseDoubleClickEvent(event)


class DayTimeline(QWidget):
    row_height = 38
    top_padding = 10
    bottom_padding = 10
    label_width = 54
    event_gap = 5

    def __init__(self, events, is_today, on_add, on_edit, on_delete):
        super().__init__()
        self.events = events
        self.is_today = is_today
        self.on_add = on_add
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.blocks = []
        self.selecting = False
        self.selection_start_x = None
        self.selection_start_y = None
        self.selection_current_x = None
        self.selection_current_y = None
        self.setObjectName("dayTimeline")
        self.setMinimumHeight(self.top_padding + self.row_height * 24 + self.bottom_padding)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.build_blocks()

    def build_blocks(self):
        for block in self.blocks:
            block.deleteLater()
        self.blocks = []

        for event in self.events:
            block = TimelineEventBlock(event, self.on_edit, self.on_delete, self)
            self.blocks.append(block)

        self.layout_blocks()

    def resizeEvent(self, event):
        self.layout_blocks()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        y = event.position().y() - self.top_padding
        if y < 0:
            return

        selection_left, selection_width = self.selection_area_rect()
        if event.position().x() < selection_left or event.position().x() > selection_left + selection_width:
            return

        self.begin_selection(event.position().x(), event.position().y())

    def begin_selection(self, x, y):
        self.selecting = True
        self.selection_start_x = self.clamp_timeline_x(x)
        self.selection_start_y = self.clamp_timeline_y(y)
        self.selection_current_x = self.selection_start_x
        self.selection_current_y = self.selection_start_y
        self.update()

    def update_selection(self, x, y):
        if not self.selecting:
            return
        self.selection_current_x = self.clamp_timeline_x(x)
        self.selection_current_y = self.clamp_timeline_y(y)
        self.update()

    def finish_selection(self, y):
        if not self.selecting:
            return

        start_y = self.selection_start_y
        end_y = self.clamp_timeline_y(y)
        self.selecting = False
        self.selection_start_x = None
        self.selection_start_y = None
        self.selection_current_x = None
        self.selection_current_y = None
        self.update()

        if start_y is None:
            return

        if abs(end_y - start_y) < 8:
            hour = self.hour_floor_from_y(start_y)
            if 0 <= hour <= 23:
                self.on_add(hour)
            return

        top_y = min(start_y, end_y)
        bottom_y = max(start_y, end_y)
        start_hour = self.hour_floor_from_y(top_y)
        end_hour = self.hour_ceil_from_y(bottom_y)

        start_hour = max(0, min(23, start_hour))
        end_hour = max(start_hour + 1, min(24, end_hour))
        self.on_add(start_hour, end_hour)

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.update_selection(event.position().x(), event.position().y())
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.selecting or event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return

        self.finish_selection(event.position().y())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        line_pen = QPen(QColor("#E5E7EB"))
        text_pen = QPen(QColor("#6B7280"))
        current_fill = QColor("#EAF3FF")

        current_hour = datetime.now().hour if self.is_today else None
        if current_hour is not None:
            y = self.top_padding + current_hour * self.row_height
            painter.fillRect(self.label_width, y, width - self.label_width, self.row_height, current_fill)

        selection_left, selection_width = self.selection_area_rect()
        painter.fillRect(selection_left, self.top_padding, selection_width, self.row_height * 24, QColor(255, 255, 255, 115))
        painter.setPen(QPen(QColor("#D1D5DB")))
        painter.drawLine(selection_left, self.top_padding, selection_left, self.top_padding + self.row_height * 24)

        if (
            self.selecting
            and self.selection_start_x is not None
            and self.selection_current_x is not None
            and self.selection_start_y is not None
            and self.selection_current_y is not None
        ):
            left_bound, event_width = self.selection_area_rect()
            right_bound = left_bound + event_width
            left = int(max(left_bound, min(self.selection_start_x, self.selection_current_x)))
            right = int(min(right_bound, max(self.selection_start_x, self.selection_current_x)))
            top_y = int(min(self.selection_start_y, self.selection_current_y))
            bottom_y = int(max(self.selection_start_y, self.selection_current_y))
            if right - left < 18:
                right = min(right_bound, left + max(120, event_width // 3))
            if bottom_y - top_y < 8:
                bottom_y = top_y + self.row_height
            painter.fillRect(left, top_y, right - left, bottom_y - top_y, QColor(37, 99, 235, 34))
            painter.setPen(QPen(QColor("#2563EB"), 2))
            painter.drawRect(left, top_y, right - left, bottom_y - top_y)

        painter.setFont(QFont("Microsoft YaHei UI", 9))
        for hour in range(25):
            y = self.top_padding + hour * self.row_height
            painter.setPen(line_pen)
            painter.drawLine(self.label_width, y, width - 4, y)

            if hour < 24:
                painter.setPen(QPen(QColor("#2563EB") if hour == current_hour else text_pen.color()))
                painter.drawText(0, y - 1, self.label_width - 8, 22, Qt.AlignRight | Qt.AlignTop, f"{hour:02d}:00")

        super().paintEvent(event)

    def clamp_timeline_y(self, y):
        min_y = self.top_padding
        max_y = self.top_padding + self.row_height * 24
        return max(min_y, min(max_y, y))

    def clamp_timeline_x(self, x):
        left, width = self.selection_area_rect()
        right = left + width
        return max(left, min(right, x))

    def hour_floor_from_y(self, y):
        return int((y - self.top_padding) // self.row_height)

    def hour_ceil_from_y(self, y):
        relative = max(0, y - self.top_padding)
        return int((relative + self.row_height - 1) // self.row_height)

    def event_area_rect(self):
        left = self.label_width + 8
        right_padding = 8
        total_width = max(120, self.width() - left - right_padding)
        selection_width = max(90, int(total_width / 3))
        event_width = max(80, total_width - selection_width - self.event_gap)
        event_left = left + selection_width + self.event_gap
        return event_left, event_width

    def selection_area_rect(self):
        left = self.label_width + 8
        right_padding = 8
        total_width = max(120, self.width() - left - right_padding)
        selection_width = max(90, int(total_width / 3))
        return left, selection_width

    def layout_blocks(self):
        if not self.blocks:
            return

        positions = self.calculate_positions(self.events)
        left, total_width = self.event_area_rect()

        for block, event in zip(self.blocks, self.events):
            column, column_count = positions[event["id"]]
            block_gap = self.event_gap
            column_width = (total_width - block_gap * (column_count - 1)) / column_count
            x = int(left + column * (column_width + block_gap))
            y = int(self.top_padding + event["start_hour"] * self.row_height + 2)
            width = int(column_width)
            height = int(max(28, event.get("duration", 1) * self.row_height - 4))
            block.setGeometry(x, y, width, height)
            block.show()

    def calculate_positions(self, events):
        sorted_events = sorted(events, key=lambda item: (item["start_hour"], item["start_hour"] + item.get("duration", 1)))
        groups = []
        current_group = []
        current_end = None

        for event in sorted_events:
            start = event["start_hour"]
            end = min(24, start + event.get("duration", 1))
            if not current_group or start < current_end:
                current_group.append(event)
                current_end = max(current_end or end, end)
            else:
                groups.append(current_group)
                current_group = [event]
                current_end = end

        if current_group:
            groups.append(current_group)

        positions = {}
        for group in groups:
            column_ends = []
            assigned = {}

            for event in group:
                start = event["start_hour"]
                end = min(24, start + event.get("duration", 1))
                column = None

                for index, column_end in enumerate(column_ends):
                    if start >= column_end:
                        column = index
                        column_ends[index] = end
                        break

                if column is None:
                    column = len(column_ends)
                    column_ends.append(end)

                assigned[event["id"]] = column

            column_count = max(1, len(column_ends))
            for event_id, column in assigned.items():
                positions[event_id] = (column, column_count)

        return positions


class HourRow(Card):
    def __init__(self, hour, events, is_current_hour, on_add, on_edit, on_delete):
        super().__init__()
        self.hour = hour
        self.on_add = on_add

        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("currentHourRow" if is_current_hour else "hourRow")
        self.setMinimumHeight(34)

        root = QHBoxLayout(self)
        root.setContentsMargins(6, 3, 6, 3)
        root.setSpacing(10)

        time_box = QVBoxLayout()
        time_box.setSpacing(0)
        time_box.setAlignment(Qt.AlignTop)

        time_label = QLabel(f"{hour:02d}:00")
        time_label.setObjectName("currentTimeLabel" if is_current_hour else "timeLabel")
        time_box.addWidget(time_label)

        if is_current_hour:
            now_label = QLabel("现在")
            now_label.setObjectName("nowLabel")
            time_box.addWidget(now_label)

        time_holder = QWidget()
        time_holder.setFixedWidth(54)
        time_holder.setLayout(time_box)
        root.addWidget(time_holder)

        event_shell = QVBoxLayout()
        event_shell.setSpacing(3)

        event_area = QVBoxLayout()
        event_area.setSpacing(4)

        if events:
            for event in events:
                event_area.addWidget(EventPill(event, on_edit, on_delete))
        else:
            empty = QLabel("")
            empty.setObjectName("emptyLabel")
            empty.setFixedHeight(20)
            event_area.addWidget(empty)

        event_shell.addLayout(event_area)
        root.addLayout(event_shell, stretch=1)

    def mousePressEvent(self, event):
        child = self.childAt(event.position().toPoint())
        while child is not None and child is not self:
            if isinstance(child, (QPushButton, EventPill)):
                return
            child = child.parentWidget()

        if isinstance(child, QPushButton):
            return
        if event.button() == Qt.LeftButton:
            self.on_add(self.hour)
        super().mousePressEvent(event)


class EventPill(QFrame):
    def __init__(self, event, on_edit, on_delete):
        super().__init__()
        self.event_data = event
        self.on_edit = on_edit
        self.setObjectName("eventPill")
        self.setCursor(Qt.PointingHandCursor)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 6, 0)
        root.setSpacing(7)

        bar = QFrame()
        bar.setObjectName("eventColorBar")
        bar.setStyleSheet(f"background: {event.get('color', '#3B82F6')}; border-radius: 4px;")
        bar.setFixedWidth(6)
        root.addWidget(bar)

        info = QVBoxLayout()
        info.setContentsMargins(0, 5, 0, 5)
        info.setSpacing(1)

        title = QLabel(event["title"])
        title.setObjectName("eventTitle")
        title.setWordWrap(True)

        info.addWidget(title)
        root.addLayout(info, stretch=1)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_edit(self.event_data)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.on_edit(self.event_data)
        super().mouseDoubleClickEvent(event)


class OverviewEventButton(QPushButton):
    def __init__(self, event, on_edit):
        super().__init__(event["title"])
        self.event_data = event
        self.on_edit = on_edit
        self.setObjectName("overviewEventButton")
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(lambda: self.on_edit(self.event_data))

        color = event.get("color", "#3B82F6")
        self.setStyleSheet(
            f"""
            QPushButton {{
                color: #111827;
                background: {rgba_from_hex(color, 28)};
                border: 1px solid {rgba_from_hex(color, 85)};
                border-left: 4px solid {color};
                border-radius: 8px;
                padding: 5px 7px;
                text-align: left;
                font-size: 11px;
                font-weight: 650;
            }}
            QPushButton:hover {{
                background: {rgba_from_hex(color, 42)};
            }}
            """
        )

    def mouseDoubleClickEvent(self, event):
        self.on_edit(self.event_data)
        event.accept()
        super().mouseDoubleClickEvent(event)


class MonthEventMarker(QWidget):
    def __init__(self, event, on_edit):
        super().__init__()
        self.event_data = event
        self.on_edit = on_edit
        self.color = QColor(event.get("color", "#3B82F6"))
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(12)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_edit(self.event_data)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)

        center_y = self.height() / 2
        painter.setBrush(self.color)
        painter.drawEllipse(QRectF(0, center_y - 3, 6, 6))

        bar_color = QColor(self.color)
        bar_color.setAlpha(170)
        painter.setBrush(bar_color)
        painter.drawRoundedRect(QRectF(14, center_y - 3, max(18, self.width() - 16), 6), 3, 3)


class DayOverviewCard(Card):
    def __init__(self, day, events, on_add, on_edit, compact=False):
        super().__init__()
        self.day = day
        self.on_add = on_add
        self.setObjectName("overviewDayCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(122 if compact else 210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        title = QLabel(f"{day.day}  {weekday_names[day.weekday()]}")
        title.setObjectName("overviewDayTitle")
        if day == date.today():
            title.setProperty("today", True)
        layout.addWidget(title)

        if compact and events:
            count = QLabel(f"{len(events)} 个日程")
            count.setObjectName("overviewDayCount")
            layout.addWidget(count)

        visible_count = 3 if compact else 7
        for event in events[:visible_count]:
            if compact:
                layout.addWidget(MonthEventMarker(event, on_edit))
            else:
                layout.addWidget(OverviewEventButton(event, on_edit))

        if len(events) > visible_count:
            more = QLabel(f"还有 {len(events) - visible_count} 个")
            more.setObjectName("overviewMore")
            layout.addWidget(more)

        layout.addStretch()

    def mousePressEvent(self, event):
        child = self.childAt(event.position().toPoint())
        while child is not None and child is not self:
            if isinstance(child, QPushButton):
                return
            child = child.parentWidget()

        if event.button() == Qt.LeftButton:
            self.on_add(self.day, 9)
        super().mousePressEvent(event)


class WeekOverview(QWidget):
    def __init__(self, start_day, events, on_add, on_edit):
        super().__init__()
        self.setObjectName("overviewRoot")
        self.setMinimumWidth(860)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        events_by_day = {}
        for event in events:
            events_by_day.setdefault(date.fromisoformat(event["date"]), []).append(event)

        for index in range(7):
            day = start_day + timedelta(days=index)
            card = DayOverviewCard(day, events_by_day.get(day, []), on_add, on_edit, compact=False)
            layout.addWidget(card, 0, index)
            layout.setColumnStretch(index, 1)


class MonthOverview(QWidget):
    def __init__(self, selected_day, events, on_add, on_edit):
        super().__init__()
        self.setObjectName("overviewRoot")
        self.setMinimumWidth(780)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for column, name in enumerate(weekday_names):
            label = QLabel(name)
            label.setObjectName("monthWeekdayLabel")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, 0, column)

        first_day = date(selected_day.year, selected_day.month, 1)
        days_in_month = calendar.monthrange(selected_day.year, selected_day.month)[1]
        first_column = first_day.weekday()

        events_by_day = {}
        for event in events:
            events_by_day.setdefault(date.fromisoformat(event["date"]), []).append(event)

        row = 1
        column = first_column
        for day_number in range(1, days_in_month + 1):
            day = date(selected_day.year, selected_day.month, day_number)
            card = DayOverviewCard(day, events_by_day.get(day, []), on_add, on_edit, compact=True)
            layout.addWidget(card, row, column)
            layout.setColumnStretch(column, 1)

            column += 1
            if column == 7:
                column = 0
                row += 1

        for column in range(7):
            layout.setColumnStretch(column, 1)


class CalendarScrollArea(QScrollArea):
    def __init__(self):
        super().__init__()
        self.horizontal_wheel_enabled = False

    def set_horizontal_wheel_enabled(self, enabled):
        self.horizontal_wheel_enabled = enabled

    def wheelEvent(self, event):
        horizontal_bar = self.horizontalScrollBar()
        if self.horizontal_wheel_enabled and horizontal_bar.maximum() > 0:
            delta = event.angleDelta().y() or event.angleDelta().x()
            if delta:
                horizontal_bar.setValue(horizontal_bar.value() - delta)
                event.accept()
                return

        super().wheelEvent(event)


class DateWheelOverlay(QWidget):
    def __init__(self, owner):
        super().__init__(owner.window(), Qt.Tool | Qt.FramelessWindowHint)
        self.owner = owner
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName("dateWheelOverlay")
        self.setFixedSize(128, 132)
        self.values = []

    def set_values(self, values):
        self.values = values
        self.update()

    def wheelEvent(self, event):
        self.owner.step_day_from_wheel(event)

    def leaveEvent(self, event):
        QTimer.singleShot(120, self.owner.hide_overlay_if_idle)
        super().leaveEvent(event)

    def paintEvent(self, event):
        if not self.values:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        panel = QRectF(1, 1, self.width() - 2, self.height() - 2)
        painter.setPen(QPen(QColor(147, 197, 253, 150), 1))
        painter.setBrush(QColor(247, 250, 255, 225))
        painter.drawRoundedRect(panel, 22, 22)

        center_x = 82
        center_y = self.height() / 2
        radius = 58
        arc_rect = QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
        painter.setPen(QPen(QColor(147, 197, 253, 105), 1))
        painter.drawArc(arc_rect, 90 * 16, 180 * 16)

        angles = (118, 150, 180, 210, 242)
        for index, (value, angle) in enumerate(zip(self.values, angles)):
            radians = math.radians(angle)
            x = center_x + radius * math.cos(radians)
            y = center_y + radius * math.sin(radians)
            self.draw_value_bubble(painter, x, y, value, index == 2)

    def draw_value_bubble(self, painter, x, y, value, selected):
        size = 28
        rect = QRectF(x - size / 2, y - size / 2, size, size)
        if selected:
            painter.setPen(QPen(QColor(37, 99, 235), 1.6))
            painter.setBrush(QColor(255, 255, 255, 235))
            color = QColor("#2563EB")
            font_size = 14
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 155), 1))
            painter.setBrush(QColor(255, 255, 255, 112))
            color = QColor(37, 99, 235, 112)
            font_size = 12

        painter.drawEllipse(rect)
        painter.setPen(QPen(color))
        painter.setFont(QFont("Microsoft YaHei UI", font_size, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, str(value))


class DateWheelButton(QPushButton):
    def __init__(self, get_date, on_day_changed, on_click, parent=None):
        super().__init__(parent)
        self.get_date = get_date
        self.on_day_changed = on_day_changed
        self.values = []
        self.overlay = DateWheelOverlay(self)
        self.setObjectName("viewButton")
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(on_click)
        self.setFixedSize(34, 34)
        self.refresh()

    def refresh(self):
        current = self.get_date()
        self.setText(str(current.day) if self.underMouse() else "日")
        offsets = (-2, -1, 0, 1, 2)
        days_in_month = calendar.monthrange(current.year, current.month)[1]
        self.values = [((current.day - 1 + offset) % days_in_month) + 1 for offset in offsets]
        self.overlay.set_values(self.values)
        if self.underMouse() and not self.overlay.isVisible():
            self.show_overlay()
        self.update()

    def enterEvent(self, event):
        self.refresh()
        self.show_overlay()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setText("日")
        QTimer.singleShot(120, self.hide_overlay_if_idle)
        super().leaveEvent(event)

    def wheelEvent(self, event):
        self.step_day_from_wheel(event)

    def step_day_from_wheel(self, event):
        current = self.get_date()
        days_in_month = calendar.monthrange(current.year, current.month)[1]
        step = 1 if event.angleDelta().y() < 0 else -1
        next_day = ((current.day - 1 + step) % days_in_month) + 1
        self.on_day_changed(next_day)
        self.refresh()
        event.accept()

    def show_overlay(self):
        button_center = self.mapToGlobal(self.rect().center())
        self.overlay.move(button_center.x() - 12, button_center.y() - self.overlay.height() // 2)
        self.overlay.raise_()
        self.overlay.show()

    def hide_overlay_if_idle(self):
        if self.underMouse() or self.overlay.underMouse():
            return
        self.overlay.hide()


class CalendarWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = EventStore(EVENTS_FILE)
        self.selected_date = date.today()
        self.view_mode = "day"
        self.view_buttons = {}
        self.history = []
        self.compact_size = (430, 720)

        self.setWindowTitle("MyCalendar")
        self.resize(*self.compact_size)
        self.setMinimumSize(390, 560)

        self.build()
        self.render()

    def build(self):
        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.date_label = QLabel()
        self.date_label.setObjectName("dateLabel")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("subtitleLabel")
        title_box.addWidget(self.date_label)
        title_box.addWidget(self.subtitle_label)

        header.addLayout(title_box, stretch=1)

        self.size_button = QPushButton("全屏")
        self.size_button.setObjectName("chipButton")
        self.size_button.clicked.connect(self.toggle_size)

        header.addWidget(self.size_button)
        root.addLayout(header)

        nav = QHBoxLayout()
        nav.setSpacing(5)

        back_button = QPushButton("返回")
        back_button.setObjectName("navButton")
        back_button.clicked.connect(self.go_back)

        today_button = QPushButton("今天")
        today_button.setObjectName("navButton")
        today_button.clicked.connect(self.go_today)

        self.period_prev_button = QPushButton("‹")
        self.period_prev_button.setObjectName("navButton")
        self.period_prev_button.clicked.connect(lambda: self.shift_period(-1))

        self.period_label_button = QPushButton("")
        self.period_label_button.setObjectName("periodButton")

        self.period_next_button = QPushButton("›")
        self.period_next_button.setObjectName("navButton")
        self.period_next_button.clicked.connect(lambda: self.shift_period(1))

        self.date_wheel_button = DateWheelButton(
            lambda: self.selected_date,
            self.change_day_in_current_month,
            lambda: self.set_view_mode("day"),
        )
        self.view_buttons["day"] = self.date_wheel_button

        view_switch = QHBoxLayout()
        view_switch.setSpacing(2)
        week_button = QPushButton("周")
        week_button.setObjectName("viewButton")
        week_button.clicked.connect(lambda: self.set_view_mode("week"))

        month_button = QPushButton("月")
        month_button.setObjectName("viewButton")
        month_button.clicked.connect(lambda: self.set_view_mode("month"))

        self.view_buttons["week"] = week_button
        self.view_buttons["month"] = month_button
        view_switch.addWidget(week_button)
        view_switch.addWidget(month_button)

        nav.addWidget(back_button)
        nav.addWidget(today_button)
        nav.addWidget(self.date_wheel_button)
        nav.addWidget(self.period_prev_button)
        nav.addWidget(self.period_label_button)
        nav.addWidget(self.period_next_button)
        nav.addStretch()
        nav.addLayout(view_switch)
        root.addLayout(nav)

        self.scroll = CalendarScrollArea()
        self.scroll.setObjectName("timelineScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.timeline = QWidget()
        self.timeline.setObjectName("timeline")
        self.timeline_layout = QVBoxLayout(self.timeline)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(0)
        self.scroll.setWidget(self.timeline)

        root.addWidget(self.scroll, stretch=1)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.show_compact()
            return
        if event.key() == Qt.Key_F11:
            self.toggle_size()
            return
        if event.key() == Qt.Key_N and event.modifiers() & Qt.ControlModifier:
            self.open_dialog(datetime.now().hour)
            return
        if event.key() == Qt.Key_T and event.modifiers() & Qt.ControlModifier:
            self.go_today()
            return
        super().keyPressEvent(event)

    def toggle_size(self):
        if self.isMaximized():
            self.show_compact()
        else:
            self.size_button.setText("小窗")
            self.showMaximized()

    def show_compact(self):
        self.size_button.setText("全屏")
        self.showNormal()
        self.resize(*self.compact_size)

    def current_page_state(self):
        return self.selected_date, self.view_mode

    def push_history(self):
        state = self.current_page_state()
        if not self.history or self.history[-1] != state:
            self.history.append(state)

    def go_back(self):
        if not self.history:
            return

        self.selected_date, self.view_mode = self.history.pop()
        if self.view_mode == "month" and not self.isMaximized():
            self.size_button.setText("小窗")
            self.showMaximized()
        self.render()

    def go_today(self):
        target = (date.today(), "day")
        if self.current_page_state() != target:
            self.push_history()
        self.selected_date = date.today()
        self.view_mode = "day"
        self.render()

    def set_view_mode(self, mode):
        if self.view_mode != mode:
            self.push_history()
        self.view_mode = mode
        if mode == "month" and not self.isMaximized():
            self.size_button.setText("小窗")
            self.showMaximized()
        self.render()

    def change_day_in_current_month(self, day):
        target = (date(self.selected_date.year, self.selected_date.month, day), "day")
        if self.current_page_state() != target:
            self.push_history()
        self.selected_date = date(self.selected_date.year, self.selected_date.month, day)
        self.view_mode = "day"
        self.render()

    def shift_period(self, amount):
        self.push_history()
        if self.view_mode == "month":
            self.selected_date = self.add_months(self.selected_date, amount)
        elif self.view_mode == "week":
            self.selected_date += timedelta(days=amount * 7)
        self.render()

    def month_week_index(self):
        first_day = date(self.selected_date.year, self.selected_date.month, 1)
        first_monday = first_day - timedelta(days=first_day.weekday())
        current_monday = self.selected_date - timedelta(days=self.selected_date.weekday())
        return ((current_monday - first_monday).days // 7) + 1

    def update_period_nav(self):
        visible = self.view_mode in ("week", "month")
        for button in (self.period_prev_button, self.period_label_button, self.period_next_button):
            button.setVisible(visible)

        if self.view_mode == "month":
            self.period_label_button.setText(f"{self.selected_date.month}月")
        elif self.view_mode == "week":
            self.period_label_button.setText(f"{self.selected_date.month}月第{self.month_week_index()}周")

    def refresh_view_buttons(self):
        self.update_period_nav()
        for mode, button in self.view_buttons.items():
            active = mode == self.view_mode
            button.setProperty("active", active)
            if hasattr(button, "refresh"):
                button.refresh()
            button.style().unpolish(button)
            button.style().polish(button)

    def move_day(self, amount):
        self.push_history()
        if self.view_mode == "week":
            self.selected_date += timedelta(days=amount * 7)
        elif self.view_mode == "month":
            self.selected_date = self.add_months(self.selected_date, amount)
        else:
            self.selected_date += timedelta(days=amount)
        self.render()

    def add_months(self, source_day, amount):
        month = source_day.month - 1 + amount
        year = source_day.year + month // 12
        month = month % 12 + 1
        day = min(source_day.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    def open_dialog(self, hour, event=None, dialog_date=None, end_hour=None):
        target_date = dialog_date or self.selected_date
        dialog = EventDialog(
            self,
            target_date,
            hour,
            self.save_event,
            event,
            end_hour=end_hour,
            on_delete=self.delete_event,
        )
        dialog.exec()

    def edit_event(self, event):
        self.open_dialog(event["start_hour"], event, date.fromisoformat(event["date"]))

    def add_event_for_day(self, day, hour=9):
        if self.selected_date != day:
            self.push_history()
        self.selected_date = day
        self.open_dialog(hour, None, day)

    def open_day_view(self, day, _hour=9):
        target = (day, "day")
        if self.current_page_state() != target:
            self.push_history()
        self.selected_date = day
        self.view_mode = "day"
        self.render()

    def save_event(self, event, event_id=None):
        if event_id:
            self.store.update(event_id, event)
        else:
            self.store.add(event)
        self.render()

    def delete_event(self, event):
        result = QMessageBox.question(
            self,
            "删除日程",
            f"确定删除“{event['title']}”吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if result == QMessageBox.Yes:
            self.store.delete(event["id"])
            self.render()
            return True

        return False

    def clear_timeline(self):
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def render(self):
        self.clear_timeline()
        self.refresh_view_buttons()
        self.date_wheel_button.refresh()

        weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        weekday = weekday_names[self.selected_date.weekday()]
        is_today = self.selected_date == date.today()

        if self.view_mode == "week":
            self.render_week_view()
            return
        if self.view_mode == "month":
            self.scroll.set_horizontal_wheel_enabled(False)
            self.render_month_view()
            return

        self.scroll.set_horizontal_wheel_enabled(False)
        self.date_label.setText(self.selected_date.strftime("%m月%d日"))
        self.subtitle_label.setText(f"{weekday}  {'今天' if is_today else self.selected_date.strftime('%Y年%m月%d日')}")
        day_events = self.store.events_for_day(self.selected_date)
        self.render_summary(
            f"今日共有 {len(day_events)} 个日程",
            "点击空白时间添加日程，日程块按时长占据对应区域。",
        )

        timeline = DayTimeline(
            events=day_events,
            is_today=is_today,
            on_add=lambda hour, end_hour=None: self.open_dialog(hour, end_hour=end_hour),
            on_edit=self.edit_event,
            on_delete=self.delete_event,
        )
        self.timeline_layout.addWidget(timeline)
        self.timeline_layout.addStretch()
        QTimer.singleShot(0, self.scroll_day_view_to_morning)

    def scroll_day_view_to_morning(self):
        target = DayTimeline.top_padding + DayTimeline.row_height * 8
        self.scroll.verticalScrollBar().setValue(target)

    def render_summary(self, title_text, hint_text):
        summary = Card(shadow=True)
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(14, 10, 14, 10)
        summary_layout.setSpacing(2)

        summary_title = QLabel(title_text)
        summary_title.setObjectName("summaryTitle")
        summary_hint = QLabel(hint_text)
        summary_hint.setObjectName("summaryHint")
        summary_layout.addWidget(summary_title)
        summary_layout.addWidget(summary_hint)
        self.timeline_layout.addWidget(summary)
        self.timeline_layout.addSpacing(8)

    def render_week_view(self):
        self.scroll.set_horizontal_wheel_enabled(True)
        start_day = self.selected_date - timedelta(days=self.selected_date.weekday())
        end_day = start_day + timedelta(days=6)
        week_events = self.store.events_between(start_day, end_day)

        self.date_label.setText(f"{start_day.strftime('%m月%d日')} - {end_day.strftime('%m月%d日')}")
        self.subtitle_label.setText(f"{self.selected_date.year}年 第{self.selected_date.isocalendar().week}周")
        self.render_summary(
            f"本周共有 {len(week_events)} 个日程",
            "点击某一天跳转到当天日视图，点击日程可以编辑。",
        )

        overview = WeekOverview(
            start_day=start_day,
            events=week_events,
            on_add=self.open_day_view,
            on_edit=self.edit_event,
        )
        self.timeline_layout.addWidget(overview)
        self.timeline_layout.addStretch()

    def render_month_view(self):
        first_day = date(self.selected_date.year, self.selected_date.month, 1)
        last_day = date(
            self.selected_date.year,
            self.selected_date.month,
            calendar.monthrange(self.selected_date.year, self.selected_date.month)[1],
        )
        month_events = self.store.events_between(first_day, last_day)

        self.date_label.setText(self.selected_date.strftime("%Y年%m月"))
        self.subtitle_label.setText(f"整月总览  {len(month_events)} 个日程")
        self.render_summary(
            f"本月共有 {len(month_events)} 个日程",
            "点击某一天跳转到当天日视图，点击日程可以编辑。",
        )

        overview = MonthOverview(
            selected_day=self.selected_date,
            events=month_events,
            on_add=self.open_day_view,
            on_edit=self.edit_event,
        )
        self.timeline_layout.addWidget(overview)

        self.timeline_layout.addStretch()


def apply_theme(app):
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet(
        """
        QWidget {
            font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
            color: #111827;
        }

        #appRoot, #timeline {
            background: #F5F5F7;
        }

        #dayTimeline {
            background: transparent;
        }

        #overviewRoot {
            background: transparent;
        }

        #dateLabel {
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0px;
        }

        #subtitleLabel, #summaryHint, #fieldLabel, #emptyLabel {
            color: #6B7280;
        }

        #dialogTitle {
            font-size: 22px;
            font-weight: 700;
        }

        #dialogSection {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 14px;
        }

        #sectionLabel {
            color: #111827;
            font-size: 13px;
            font-weight: 700;
        }

        #subtitleLabel {
            font-size: 12px;
        }

        #card {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 14px;
        }

        #overviewDayCard {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
        }

        #overviewDayCard:hover {
            border: 1px solid #BFDBFE;
            background: #FBFDFF;
        }

        #overviewDayTitle {
            font-size: 13px;
            font-weight: 750;
        }

        #overviewDayTitle[today="true"] {
            color: #2563EB;
        }

        #overviewDayCount, #overviewMore {
            color: #6B7280;
            font-size: 11px;
        }

        #monthWeekdayLabel {
            color: #6B7280;
            font-size: 11px;
            font-weight: 700;
        }

        #hourRow, #currentHourRow {
            background: transparent;
            border: none;
            border-bottom: 1px solid #E5E7EB;
            border-radius: 0px;
        }

        #hourRow:hover {
            background: #FFFFFF;
        }

        #currentHourRow {
            background: #EEF6FF;
            border-bottom: 1px solid #BFDBFE;
        }

        #summaryTitle {
            font-size: 15px;
            font-weight: 700;
        }

        #summaryHint {
            font-size: 12px;
        }

        #timeLabel, #currentTimeLabel {
            font-size: 12px;
            font-weight: 600;
        }

        #currentTimeLabel, #nowLabel {
            color: #2563EB;
        }

        #nowLabel {
            font-size: 10px;
            font-weight: 600;
        }

        #eventPill {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 8px;
        }

        #eventTitle {
            font-size: 12px;
            font-weight: 700;
        }

        #timelineEventTitle {
            font-size: 12px;
            font-weight: 700;
            color: #111827;
        }

        QPushButton {
            border: none;
            border-radius: 11px;
            padding: 8px 11px;
            font-weight: 650;
        }

        #primaryButton {
            color: white;
            background: #2563EB;
        }

        #primaryButton:hover {
            background: #1D4ED8;
        }

        #dialogDeleteButton {
            color: #FFFFFF;
            background: #DC2626;
            border: 1px solid #DC2626;
        }

        #dialogDeleteButton:hover {
            background: #B91C1C;
            border: 1px solid #B91C1C;
        }

        #secondaryButton, #chipButton, #navButton, #periodButton, #inlineAddButton, #viewButton {
            color: #374151;
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
        }

        #secondaryButton:hover, #chipButton:hover, #navButton:hover, #periodButton:hover, #inlineAddButton:hover, #viewButton:hover {
            background: #F3F4F6;
        }

        #viewButton {
            min-width: 28px;
            padding: 6px 7px;
            border-radius: 9px;
        }

        #viewButton[active="true"] {
            color: #FFFFFF;
            background: #2563EB;
            border: 1px solid #2563EB;
        }

        #inlineAddButton {
            color: #2563EB;
            background: #EFF6FF;
            border: 1px solid #DBEAFE;
            padding: 6px 10px;
            font-size: 12px;
            border-radius: 9px;
        }

        #inlineAddButton:hover {
            background: #DBEAFE;
        }

        #chipButton[active="true"] {
            color: #1D4ED8;
            background: #DBEAFE;
            border: 1px solid #BFDBFE;
        }

        #navButton {
            min-width: 30px;
            padding: 6px 8px;
            border-radius: 9px;
        }

        #periodButton {
            min-width: 58px;
            padding: 6px 10px;
            border-radius: 9px;
            font-weight: 750;
            color: #2563EB;
        }

        QLineEdit, QTextEdit {
            background: #F3F4F6;
            border: 1px solid transparent;
            border-radius: 12px;
            padding: 9px 11px;
            selection-background-color: #93C5FD;
        }

        QLineEdit:focus, QTextEdit:focus {
            background: #FFFFFF;
            border: 1px solid #93C5FD;
        }

        #timeWheel {
            background: #F3F4F6;
            border: 1px solid transparent;
            border-radius: 12px;
            padding: 6px;
            outline: none;
        }

        #timeWheel:focus {
            background: #FFFFFF;
            border: 1px solid #93C5FD;
        }

        #timeWheel::item {
            color: #6B7280;
            border-radius: 9px;
        }

        #timeWheel::item:selected {
            color: #111827;
            background: #FFFFFF;
            border: 1px solid #DBEAFE;
            font-weight: 700;
        }

        QTextEdit {
            min-height: 150px;
        }

        QScrollArea {
            background: transparent;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 10px;
            margin: 2px;
        }

        QScrollBar::handle:vertical {
            background: #D1D5DB;
            border-radius: 5px;
            min-height: 40px;
        }

        QScrollBar::handle:vertical:hover {
            background: #9CA3AF;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        QMessageBox {
            background: #FFFFFF;
        }
        """
    )


def main():
    app = QApplication(sys.argv)
    apply_theme(app)

    window = CalendarWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
