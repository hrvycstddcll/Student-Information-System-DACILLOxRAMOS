import sys
import os
import sqlite3
import calendar
from datetime import date, timedelta

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem
)
from PyQt5.QtGui import (
    QPixmap, QFont, QFontDatabase,
    QPainter, QPen, QColor, QPainterPath, QBrush
)
from PyQt5.QtCore import (
    Qt, QEvent, QTimer, QDate, QRectF,
    QPropertyAnimation, QEasingCurve, QRect,
    pyqtSignal
)


# ── PH Holidays ───────────────────────────────────────────────────────────────
PH_HOLIDAYS_2026 = {
    date(2026,  1,  1): "New Year's Day",
    date(2026,  2, 25): "EDSA People Power Revolution Anniversary",
    date(2026,  4,  2): "Maundy Thursday",
    date(2026,  4,  3): "Good Friday",
    date(2026,  4,  9): "Araw ng Kagitingan",
    date(2026,  5,  1): "Labor Day",
    date(2026,  6, 12): "Independence Day",
    date(2026,  8, 21): "Ninoy Aquino Day",
    date(2026,  8, 31): "National Heroes Day",
    date(2026, 11,  1): "All Saints' Day",
    date(2026, 11, 30): "Bonifacio Day",
    date(2026, 12, 25): "Christmas Day",
    date(2026, 12, 30): "Rizal Day",
}

# ── Palette ───────────────────────────────────────────────────────────────────
RED        = "#b90d33"
RED_DARK   = "#9f0b2d"
RED_BORDER = "#d85c79"
BG         = "#efefef"
TEXT       = "#474747"
WHITE      = "#ffffff"
SOFT       = "#f8dbe3"
SOFT2      = "#f3c4d0"

# ── DB path ───────────────────────────────────────────────────────────────────
_HERE    = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(_HERE, "database", "sis_users.db")


# ── DB helpers ────────────────────────────────────────────────────────────────
def _db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_student_count() -> int:
    try:
        with _db_conn() as c:
            row = c.execute("SELECT COUNT(*) FROM students").fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def get_enrollment_by_department() -> dict:
    """Returns {dept: count} for the bar chart."""
    try:
        with _db_conn() as c:
            rows = c.execute("""
                SELECT department, COUNT(*) as cnt
                FROM students
                GROUP BY department
                ORDER BY department
            """).fetchall()
        return {r["department"]: r["cnt"] for r in rows}
    except sqlite3.OperationalError:
        return {}


def get_enrollment_by_status() -> dict:
    """Returns {status: count} breakdown."""
    try:
        with _db_conn() as c:
            rows = c.execute("""
                SELECT status, COUNT(*) as cnt
                FROM students
                GROUP BY status
            """).fetchall()
        return {r["status"]: r["cnt"] for r in rows}
    except sqlite3.OperationalError:
        return {}


def get_recent_registrations(limit: int = 5) -> list:
    """Returns latest registered students as notification items."""
    try:
        with _db_conn() as c:
            rows = c.execute("""
                SELECT first_name, last_name, department, status
                FROM students
                ORDER BY rowid DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


# ── Toast Notification ────────────────────────────────────────────────────────
class ToastNotification(QFrame):
    """Small slide-in toast shown at bottom-right of a parent widget."""

    def __init__(self, message: str, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {RED};
                border-radius: 14px;
            }}
        """)

        lbl = QLabel(message, self)
        lbl.setStyleSheet(
            "background:transparent; border:none; color:white;"
            "font-family:'Poppins'; font-size:12px; font-weight:500;")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.adjustSize()

        pad_x, pad_y = 28, 14
        self.resize(lbl.width() + pad_x * 2, lbl.height() + pad_y * 2)
        lbl.move(pad_x, pad_y)

        # Position: bottom-right of parent
        px = parent.width()  - self.width()  - 24
        py = parent.height() - self.height() - 24
        self.move(px, py)
        self.raise_()
        self.show()

        # Fade-out after 2 s, then destroy
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._start_fade)
        self._hide_timer.start(2000)

        self._opacity = 1.0

    def _start_fade(self):
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(30)
        self._fade_timer.timeout.connect(self._fade_step)
        self._fade_timer.start()

    def _fade_step(self):
        self._opacity -= 0.07
        if self._opacity <= 0:
            self._fade_timer.stop()
            self.deleteLater()
        else:
            self.setWindowOpacity(self._opacity)
            # For child widgets use palette alpha trick via stylesheet
            alpha = max(0, int(self._opacity * 255))
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(185, 13, 51, {alpha});
                    border-radius: 14px;
                }}
            """)


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_pixmap(*names):
    for name in names:
        pix = QPixmap(name)
        if not pix.isNull():
            return pix
    return QPixmap()


# ── Reusable widgets ──────────────────────────────────────────────────────────
class OutlinePanel(QFrame):
    def __init__(self, title="", parent=None, radius=26, title_size=15):
        super().__init__(parent)
        self.title      = QLabel(title, self)
        self.radius     = radius
        self.title_size = title_size
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: 1px solid {RED_BORDER};
                border-radius: {radius}px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {RED};
                font-weight: 700;
                font-family: 'Poppins';
            }}
        """)

    def resizeEvent(self, event):
        self.title.setFont(QFont("Poppins", self.title_size, QFont.Bold))
        self.title.adjustSize()
        self.title.move(20, 12)
        super().resizeEvent(event)


class SidebarButton(QPushButton):
    def __init__(self, text="", parent=None, active=False):
        super().__init__(text, parent)
        self.active = active
        self.setCursor(Qt.PointingHandCursor)
        self.update_style()

    def update_style(self):
        if self.active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: white; color: {RED};
                    border: none; text-align: center;
                    font-family: 'Poppins'; font-size: 15px;
                    font-weight: 400; padding: 0px;
                }}
                QPushButton:hover {{ background: white; color: {RED}; }}
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: transparent; color: white;
                    border: none; text-align: center;
                    font-family: 'Poppins'; font-size: 15px;
                    font-weight: 500; padding: 0px;
                }
                QPushButton:hover { color: #ffe7ee; }
            """)

    def set_active(self, active):
        self.active = active
        self.update_style()


class HomeCard(QFrame):
    def __init__(self, title="", subtitle="", parent=None):
        super().__init__(parent)
        self.title    = QLabel(title,    self)
        self.subtitle = QLabel(subtitle, self)
        self.icon_box = QRectF()
        self._apply_style(hover=False)

    def _apply_style(self, hover=False):
        bg = RED_DARK if hover else RED
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg};
                border: 1px solid white;
                border-radius: 24px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: white;
                font-family: 'Poppins';
            }}
        """)

    def enterEvent(self, event):
        self._apply_style(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_style(hover=False)
        super().leaveEvent(event)

    def layout_card(self, icon_box, title_size, subtitle_size,
                    icon_x, icon_y, text_x, title_y, subtitle_y):
        self.icon_box = QRectF(icon_x, icon_y, icon_box, icon_box)
        self.title.setFont(QFont("Poppins", title_size, QFont.Bold))
        self.subtitle.setFont(QFont("Poppins", subtitle_size, QFont.Medium))
        self.title.adjustSize()
        self.subtitle.adjustSize()
        self.title.move(text_x, title_y)
        self.subtitle.move(text_x, subtitle_y)


# ── Enrollment Trend Widget ───────────────────────────────────────────────────
class EnrollmentChart(QWidget):
    """Bar chart of students per department + status breakdown legend."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dept_data   = {}   # {dept: count}
        self.status_data = {}   # {status: count}
        self.setAttribute(Qt.WA_TranslucentBackground)

    def refresh(self):
        self.dept_data   = get_enrollment_by_department()
        self.status_data = get_enrollment_by_status()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        pad_l, pad_r = 48, 24
        pad_t, pad_b = 36, 60   # extra bottom for labels

        chart_x = pad_l
        chart_y = pad_t
        chart_w = w - pad_l - pad_r
        chart_h = h - pad_t - pad_b

        # Background grid lines
        p.setPen(QPen(QColor("#e8d0d8"), 1, Qt.DashLine))
        grid_steps = 4
        max_val = max(self.dept_data.values(), default=1)
        max_val = max(max_val, 1)

        for i in range(grid_steps + 1):
            y = chart_y + chart_h - int(chart_h * i / grid_steps)
            p.drawLine(chart_x, y, chart_x + chart_w, y)
            val = int(max_val * i / grid_steps)
            p.setPen(QColor(TEXT))
            p.setFont(QFont("Poppins", 8))
            p.drawText(0, y - 8, pad_l - 6, 18,
                       Qt.AlignRight | Qt.AlignVCenter, str(val))
            p.setPen(QPen(QColor("#e8d0d8"), 1, Qt.DashLine))

        if not self.dept_data:
            # No data placeholder
            p.setPen(QColor(RED_BORDER))
            p.setFont(QFont("Poppins", 11))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter,
                       "No enrollment data yet.")
            p.end()
            return

        # Bars
        depts  = list(self.dept_data.keys())
        counts = list(self.dept_data.values())
        n      = len(depts)
        bar_w  = max(18, int(chart_w / n * 0.55))
        gap    = chart_w / n

        bar_colors = [
            QColor("#b90d33"), QColor("#d63060"), QColor("#e8758e"),
            QColor("#f0a8b8"), QColor("#f7cdd6"), QColor("#fde8ed"),
        ]

        for i, (dept, cnt) in enumerate(zip(depts, counts)):
            bx   = chart_x + int(i * gap + (gap - bar_w) / 2)
            bh   = int(chart_h * cnt / max_val) if max_val > 0 else 0
            by   = chart_y + chart_h - bh
            col  = bar_colors[i % len(bar_colors)]

            # Bar fill
            p.setBrush(QBrush(col))
            p.setPen(Qt.NoPen)
            path = QPainterPath()
            path.addRoundedRect(QRectF(bx, by, bar_w, bh), 6, 6)
            # Square off bottom corners
            path.addRect(QRectF(bx, by + bh - 8, bar_w, 8))
            p.drawPath(path)

            # Count label above bar
            p.setPen(QColor(RED_DARK))
            p.setFont(QFont("Poppins", 9, QFont.Bold))
            p.drawText(bx, by - 18, bar_w, 18,
                       Qt.AlignCenter, str(cnt))

            # Dept label below
            p.setPen(QColor(TEXT))
            p.setFont(QFont("Poppins", 8))
            p.drawText(bx - 10, chart_y + chart_h + 8,
                       bar_w + 20, 20, Qt.AlignCenter, dept)

        # Status legend (bottom)
        status_colors = {
            "Regular":   QColor("#b90d33"),
            "Irregular": QColor("#e8758e"),
            "Transferee":QColor("#f0a8b8"),
        }
        lx = chart_x
        ly = h - 22
        p.setFont(QFont("Poppins", 8))
        for status, cnt in self.status_data.items():
            col = status_colors.get(status, QColor(RED_BORDER))
            p.setBrush(QBrush(col))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(lx, ly, 10, 10), 2, 2)
            p.setPen(QColor(TEXT))
            label = f"{status}: {cnt}"
            p.drawText(lx + 14, ly - 1, 120, 14,
                       Qt.AlignLeft | Qt.AlignVCenter, label)
            lx += 120

        p.end()


# ── Notification Popup ────────────────────────────────────────────────────────
class NotificationPopup(QWidget):
    """Modal-style popup listing recent student registrations."""

    def __init__(self, records: list, parent=None):
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(f"""
            QWidget {{
                background: {WHITE};
                border: 1px solid {RED_BORDER};
                border-radius: 20px;
            }}
        """)

        # ── Title bar ─────────────────────────────────────────────────────────
        title = QLabel("🔔  Recent Registrations", self)
        title.setStyleSheet(
            f"background:transparent;border:none;color:{RED};"
            f"font-family:'Poppins';font-size:14px;font-weight:700;")
        title.move(24, 18)
        title.adjustSize()

        close_btn = QPushButton("✕", self)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{RED}; font-size:16px; font-weight:700;
                font-family:'Poppins';
            }}
            QPushButton:hover {{ color:{RED_DARK}; }}
        """)
        close_btn.clicked.connect(self.close)

        # ── Content ───────────────────────────────────────────────────────────
        self._list = QListWidget(self)
        self._list.setStyleSheet(f"""
            QListWidget {{
                background:transparent; border:none;
                font-family:'Poppins'; font-size:12px; color:{TEXT};
                outline:0;
            }}
            QListWidget::item {{
                padding:10px 8px;
                border-bottom:1px solid {SOFT};
            }}
            QListWidget::item:hover {{
                background:{SOFT};
                border-radius:8px;
            }}
        """)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        if not records:
            item = QListWidgetItem("  No recent registrations.")
            item.setForeground(QColor(RED_BORDER))
            self._list.addItem(item)
        else:
            for r in records:
                fname = r.get("first_name", "")
                lname = r.get("last_name", "")
                dept  = r.get("department", "")
                status= r.get("status", "")
                self._list.addItem(
                    QListWidgetItem(f"  {fname} {lname}  ·  {dept}  ·  {status}"))

        # ── Size & position ───────────────────────────────────────────────────
        popup_w, popup_h = 460, min(80 + max(len(records), 1) * 44, 420)
        self.resize(popup_w, popup_h)
        close_btn.setGeometry(popup_w - 40, 12, 28, 28)
        self._list.setGeometry(16, 52, popup_w - 32, popup_h - 68)

        # Centre on parent
        if parent:
            px = parent.x() + (parent.width()  - popup_w) // 2
            py = parent.y() + (parent.height() - popup_h) // 2
            self.move(px, py)

    def exec_(self):
        self.show()
        loop = __import__("PyQt5.QtCore", fromlist=["QEventLoop"]).QEventLoop()
        self.destroyed.connect(loop.quit)
        loop.exec_()


# ── Dashboard Window ──────────────────────────────────────────────────────────
class DashboardWindow(QWidget):
    logout_requested   = pyqtSignal()
    open_add_student   = pyqtSignal()
    open_view_students = pyqtSignal()

    def __init__(self, user: dict = None):
        super().__init__()
        self.user = user or {"id": 0, "username": "Guest",
                             "role": "guest", "email": ""}

        self.setWindowTitle("Student Information System")
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(f"background:{BG};")

        QFontDatabase.addApplicationFont("LeagueSpartan-VariableFont_wght.ttf")
        QFontDatabase.addApplicationFont("Poppins-Regular.ttf")
        QFontDatabase.addApplicationFont("Poppins-Bold.ttf")
        QFontDatabase.addApplicationFont("Poppins-SemiBold.ttf")

        self.sidebar_open  = False
        self.sidebar_anim  = None
        self.sidebar_width = 360

        self.init_ui()

        # Refresh DB-driven widgets every 30 seconds
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30_000)
        self._refresh_timer.timeout.connect(self._refresh_live_data)
        self._refresh_timer.start()
        self._refresh_live_data()   # immediate first load

    # ── Live data refresh ─────────────────────────────────────────────────────
    def _refresh_live_data(self):
        """Pull latest counts/notifications from the DB and update UI."""
        # Student count card
        count = get_student_count()
        self.students_card.subtitle.setText(str(count))
        self.students_card.subtitle.adjustSize()

        # Notification card
        recent = get_recent_registrations(5)
        notif_count = len(recent)
        if notif_count == 0:
            self.notify_card.subtitle.setText("No notifications")
        else:
            self.notify_card.subtitle.setText(
                f"{notif_count} new registration{'s' if notif_count > 1 else ''}")
        self.notify_card.subtitle.adjustSize()

        # Enrollment chart
        self.chart.refresh()

        # Repaint to show updated subtitle positions
        self.update()

    # ── UI build ──────────────────────────────────────────────────────────────
    def init_ui(self):
        # ── Sidebar ──────────────────────────────────────────────────────────
        # Dim overlay — closes sidebar when clicked
        self._dim_overlay = QFrame(self)
        self._dim_overlay.setStyleSheet("background: rgba(0,0,0,0.35);")
        self._dim_overlay.hide()
        self._dim_overlay.mousePressEvent = lambda _: self.toggle_sidebar()

        self.sidebar = QFrame(self)
        self.sidebar.hide()
        self.sidebar.setStyleSheet(f"background:{RED}; border:none;")

        self.sidebar_top    = QFrame(self.sidebar)
        self.sidebar_mid    = QFrame(self.sidebar)
        self.sidebar_bottom = QFrame(self.sidebar)
        for f in (self.sidebar_top, self.sidebar_mid, self.sidebar_bottom):
            f.setStyleSheet(f"background:{RED}; border:none;")

        self.logo_top    = QLabel(self.sidebar_top)
        self.logo_bottom = QLabel(self.sidebar_bottom)
        for lbl in (self.logo_top, self.logo_bottom):
            lbl.setScaledContents(True)

        self.bottom_student = QLabel("      Student",      self.sidebar_bottom)
        self.bottom_info    = QLabel("Information System", self.sidebar_bottom)
        self.bottom_student.setStyleSheet(
            "color:white;background:transparent;border:none;"
            "font-family:'Poppins';font-weight:700;")
        self.bottom_info.setStyleSheet(
            "color:white;background:transparent;border:none;"
            "font-family:'Poppins';font-weight:500;")

        logo_pix = load_pixmap("logo w.png", "logo_w.png", "logo w.PNG")
        self.logo_top.setPixmap(logo_pix)
        self.logo_bottom.setPixmap(logo_pix)

        # Nav buttons — Dashboard, Log Out, Exit only
        self.btn_dashboard = SidebarButton("Dashboard", self.sidebar, active=True)
        self.btn_logout    = SidebarButton("Log Out",   self.sidebar)
        self.btn_exit      = SidebarButton("Exit",      self.sidebar)

        self.sidebar_buttons = [self.btn_dashboard, self.btn_logout, self.btn_exit]

        self.btn_dashboard.clicked.connect(
            lambda: self.set_active_sidebar(self.btn_dashboard))
        self.btn_logout.clicked.connect(self._handle_logout)
        self.btn_exit.clicked.connect(self.close)

        self.set_active_sidebar(self.btn_dashboard)

        self.btn_toggle = QPushButton("☰", self)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self.toggle_sidebar)

        # ── Welcome bar ───────────────────────────────────────────────────────
        self.welcome_bar = OutlinePanel("", self, radius=26, title_size=15)

        self.welcome_l = QLabel("Welcome back, ",                    self.welcome_bar)
        self.welcome_r = QLabel(self.user.get("username", "Guest") + "!", self.welcome_bar)
        self.welcome_l.setStyleSheet(
            f"background:transparent;border:none;color:{RED};font-family:'Poppins';")
        self.welcome_r.setStyleSheet(
            f"background:transparent;border:none;color:{RED};"
            f"font-family:'Poppins';font-weight:700;")

        # ── Home cards ────────────────────────────────────────────────────────
        self.students_card = HomeCard("View all Students", "…",            self)
        self.register_card = HomeCard("Register a\nStudent", "",           self)
        self.notify_card   = HomeCard("Notifications", "Loading…",         self)

        self.students_card.mousePressEvent = lambda _: self.open_view_students.emit()
        self.register_card.mousePressEvent = lambda _: self.open_add_student.emit()
        self.notify_card.mousePressEvent   = lambda _: self._open_notifications()
        self.students_card.setCursor(Qt.PointingHandCursor)
        self.register_card.setCursor(Qt.PointingHandCursor)
        self.notify_card.setCursor(Qt.PointingHandCursor)

        # ── Lower panels ──────────────────────────────────────────────────────
        self.calendar_panel = OutlinePanel("Calendar & Activities", self,
                                           radius=26, title_size=15)
        self.graph_panel    = OutlinePanel("Enrollment Trend",      self,
                                           radius=26, title_size=15)

        # ── Enrollment chart (lives inside graph_panel) ───────────────────────
        self.chart = EnrollmentChart(self.graph_panel)

        self.cal_month = QLabel("", self.calendar_panel)
        self.cal_month.setStyleSheet(
            f"background:transparent;border:none;color:{RED};"
            f"font-family:'Poppins';font-weight:700;")

        self.prev_month = QPushButton("‹", self.calendar_panel)
        self.next_month = QPushButton("›", self.calendar_panel)
        for b in (self.prev_month, self.next_month):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: white; color: {RED};
                    border: 1px solid {RED_BORDER}; border-radius: 15px;
                    font-family:'Poppins'; font-size:18px; font-weight:700;
                }}
                QPushButton:hover {{ background:#fff5f7; }}
            """)
        self.prev_month.clicked.connect(self._month_prev)
        self.next_month.clicked.connect(self._month_next)

        self.weekday_labels = []
        for wd in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
            lbl = QLabel(wd, self.calendar_panel)
            color = RED if wd in ("Sun", "Sat") else TEXT
            lbl.setStyleSheet(
                f"background:transparent;border:none;color:{color};"
                f"font-family:'Poppins';font-weight:600;")
            self.weekday_labels.append(lbl)

        self.day_buttons = []
        for _ in range(42):
            btn = QPushButton(self.calendar_panel)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(self._day_clicked)
            self.day_buttons.append(btn)

        self.holiday_title = QLabel("Holiday / Activity", self.calendar_panel)
        self.holiday_title.setStyleSheet(
            f"background:transparent;border:none;color:{RED};"
            f"font-family:'Poppins';font-weight:700;")
        self.holiday_date = QLabel(self.calendar_panel)
        self.holiday_date.setStyleSheet(
            f"background:transparent;border:none;color:{TEXT};"
            f"font-family:'Poppins';font-weight:600;")

        self.holiday_box = QFrame(self.calendar_panel)
        self.holiday_box.setStyleSheet(
            f"background:transparent;border:1px solid {RED_BORDER};"
            f"border-radius:16px;")
        self.holiday_list = QListWidget(self.holiday_box)
        self.holiday_list.setStyleSheet("""
            QListWidget {
                background:transparent; border:none; color:#555;
                font-family:'Poppins'; font-size:12px; padding:6px;
            }
            QListWidget::item { padding:8px 4px; border-bottom:1px solid #f0d8df; }
        """)

        self.current_year   = QDate.currentDate().year()
        self.current_month  = QDate.currentDate().month()
        self.selected_qdate = QDate.currentDate()

        self._update_calendar_cells()
        self._on_date_selected(self.selected_qdate)
        self.update_positions()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def set_active_sidebar(self, active_button):
        for btn in self.sidebar_buttons:
            btn.set_active(btn is active_button)

    def _handle_logout(self):
        self.set_active_sidebar(self.btn_logout)
        self.logout_requested.emit()

    def _open_notifications(self):
        """Show popup listing recent student registrations."""
        recent = get_recent_registrations(10)
        dlg = NotificationPopup(recent, self)
        dlg.exec_()

    def _animate_sidebar(self, end_w):
        if self.sidebar_anim:
            self.sidebar_anim.stop()
        self.sidebar_anim = QPropertyAnimation(self.sidebar, b"geometry", self)
        self.sidebar_anim.setDuration(220)
        self.sidebar_anim.setStartValue(self.sidebar.geometry())
        self.sidebar_anim.setEndValue(QRect(0, 0, end_w, self.height()))
        self.sidebar_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.sidebar_anim.start()

    def toggle_sidebar(self):
        self.sidebar_open = not self.sidebar_open
        if self.sidebar_open:
            self._dim_overlay.setGeometry(0, 0, self.width(), self.height())
            self._dim_overlay.show()
            self._dim_overlay.raise_()
            self.sidebar.show()
            self._animate_sidebar(self.sidebar_width)
            self.sidebar.raise_()
            self.btn_toggle.raise_()
        else:
            self._animate_sidebar(0)
            QTimer.singleShot(220, self._close_sidebar)
        self.update_positions()

    def _close_sidebar(self):
        self.sidebar.hide()
        self._dim_overlay.hide()

    # ── Calendar ──────────────────────────────────────────────────────────────
    def _on_date_selected(self, qdate):
        self.selected_qdate = qdate
        self.holiday_date.setText(qdate.toString("dddd, MMMM d, yyyy"))
        self.holiday_date.adjustSize()
        self.holiday_list.clear()
        for item in self._entries_for(qdate.toPyDate()):
            self.holiday_list.addItem(QListWidgetItem(item))

    def _entries_for(self, dt):
        entries = []
        if dt in PH_HOLIDAYS_2026:
            entries.append(PH_HOLIDAYS_2026[dt])
        if dt.weekday() == 5:
            entries.append("Saturday")
        if dt.weekday() == 6:
            entries.append("Sunday")
        return entries or ["No holiday or activity for this date."]

    def _month_prev(self):
        if self.current_month == 1:
            self.current_month = 12;  self.current_year -= 1
        else:
            self.current_month -= 1
        self._update_calendar_cells()
        self._on_date_selected(self.selected_qdate)

    def _month_next(self):
        if self.current_month == 12:
            self.current_month = 1;  self.current_year += 1
        else:
            self.current_month += 1
        self._update_calendar_cells()
        self._on_date_selected(self.selected_qdate)

    def _day_clicked(self):
        btn = self.sender()
        qd  = btn.property("date_obj")
        if qd:
            self.selected_qdate = qd
            self._update_calendar_cells()
            self._on_date_selected(self.selected_qdate)

    def _update_calendar_cells(self):
        self.cal_month.setText(
            f"{calendar.month_name[self.current_month]} {self.current_year}")
        self.cal_month.adjustSize()

        cal = calendar.Calendar(firstweekday=6)
        month_dates = list(cal.itermonthdates(self.current_year, self.current_month))
        while len(month_dates) < 42:
            month_dates.append(month_dates[-1] + timedelta(days=1))

        for btn, dt in zip(self.day_buttons, month_dates[:42]):
            qd = QDate(dt.year, dt.month, dt.day)
            btn.setProperty("date_obj", qd)
            btn.setText(str(dt.day))

            in_month    = (dt.month == self.current_month)
            is_selected = (qd == self.selected_qdate)
            is_holiday  = dt in PH_HOLIDAYS_2026

            fg = TEXT if in_month else "#b8b8b8"
            bg = "transparent";  border = "none"

            if is_holiday:
                bg = SOFT;  fg = RED;  border = f"1px solid {RED_BORDER}"
            if is_selected:
                bg = RED;   fg = WHITE; border = "none"

            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{bg}; color:{fg}; border:{border};
                    border-radius:10px; font-family:'Poppins';
                    font-size:10px; font-weight:600;
                }}
                QPushButton:hover {{
                    background:{RED_DARK if is_selected else SOFT2};
                }}
            """)

    # ── Icon painters ─────────────────────────────────────────────────────────
    def _draw_person_icon(self, painter, rect):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(WHITE), 3))
        painter.setBrush(Qt.NoBrush)
        hr = rect.width() * 0.18
        cx = rect.center().x()
        cy = rect.top() + rect.height() * 0.28
        painter.drawEllipse(QRectF(cx - hr, cy - hr, hr * 2, hr * 2))
        body = QPainterPath()
        body.moveTo(rect.left() + rect.width() * 0.18,  rect.bottom() - rect.height() * 0.18)
        body.cubicTo(
            rect.left() + rect.width() * 0.20,  rect.top() + rect.height() * 0.58,
            rect.right() - rect.width() * 0.20, rect.top() + rect.height() * 0.58,
            rect.right() - rect.width() * 0.18, rect.bottom() - rect.height() * 0.18)
        painter.drawPath(body)
        painter.restore()

    def _draw_paper_icon(self, painter, rect):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(WHITE), 3))
        painter.setBrush(Qt.NoBrush)
        page = QRectF(rect.left() + rect.width() * 0.22,
                      rect.top()  + rect.height() * 0.16,
                      rect.width() * 0.46, rect.height() * 0.60)
        painter.drawRoundedRect(page, 4, 4)
        fold = QPainterPath()
        fold.moveTo(page.right() - 12, page.top())
        fold.lineTo(page.right(),      page.top() + 12)
        fold.lineTo(page.right() - 12, page.top() + 12)
        painter.drawPath(fold)
        for i in range(4):
            y = int(page.top() + 12 + i * 10)
            painter.drawLine(int(page.left() + 8), y, int(page.right() - 14), y)
        painter.drawLine(int(page.right() - 4),  int(page.bottom() - 2),
                         int(page.right() + 16), int(page.bottom() - 18))
        painter.drawLine(int(page.right() - 1),  int(page.bottom() + 2),
                         int(page.right() + 19), int(page.bottom() - 14))
        painter.restore()

    def _draw_bell_icon(self, painter, rect):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(WHITE), 2))
        painter.setBrush(Qt.NoBrush)
        l, t, w, h = rect.left(), rect.top(), rect.width(), rect.height()
        path = QPainterPath()
        path.moveTo(l + w * 0.28, t + h * 0.72)
        path.lineTo(l + w * 0.28, t + h * 0.45)
        path.cubicTo(l + w * 0.28, t + h * 0.18,
                     l + w * 0.72, t + h * 0.18,
                     l + w * 0.72, t + h * 0.45)
        path.lineTo(l + w * 0.72, t + h * 0.72)
        painter.drawPath(path)
        painter.drawLine(int(l + w * 0.22), int(t + h * 0.72),
                         int(l + w * 0.78), int(t + h * 0.72))
        painter.drawArc(QRectF(l + w * 0.42, t + h * 0.70,
                               w * 0.16,     h * 0.10), 0, -180 * 16)
        painter.drawEllipse(QRectF(l + w * 0.46, t + h * 0.08,
                                   w * 0.08,     h * 0.08))
        painter.restore()

    # ── Qt events ─────────────────────────────────────────────────────────────
    def resizeEvent(self, event):
        self.update_positions()
        super().resizeEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            QTimer.singleShot(0, self.update_positions)
        super().changeEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if hasattr(self.students_card, "icon_box"):
            r = self.students_card.icon_box.translated(
                self.students_card.x(), self.students_card.y())
            self._draw_person_icon(p, r)

        if hasattr(self.register_card, "icon_box"):
            r = self.register_card.icon_box.translated(
                self.register_card.x(), self.register_card.y())
            self._draw_paper_icon(p, r)

        if hasattr(self.notify_card, "icon_box"):
            r = self.notify_card.icon_box.translated(
                self.notify_card.x(), self.notify_card.y())
            self._draw_bell_icon(p, r.adjusted(4, 4, -4, -4))

        p.end()

    # ── Layout ────────────────────────────────────────────────────────────────
    def update_positions(self):
        w, h = self.width(), self.height()

        content_x = int(w * 0.08)
        content_w = int(w * 0.84)
        top_y     = int(h * 0.025)
        top_h     = int(h * 0.068)
        gap       = int(w * 0.014)
        card_y    = top_y + top_h + int(h * 0.02)
        card_h    = int(h * 0.148)
        small_w   = int((content_w - gap * 2) / 3)
        lower_y   = card_y + card_h + int(h * 0.022)
        lower_h   = h - lower_y - int(h * 0.06)
        lower_w   = int((content_w - gap) / 2)

        # Welcome bar
        self.welcome_bar.setGeometry(content_x, top_y, content_w, top_h)
        self.btn_toggle.setGeometry(18, top_y + 2, 38, 38)
        self.btn_toggle.raise_()

        if not self.sidebar_open:
            self.welcome_bar.raise_()

        ts = 10
        self.welcome_l.setFont(QFont("Poppins", ts))
        self.welcome_r.setFont(QFont("Poppins", ts, QFont.Bold))
        self.welcome_l.adjustSize()
        self.welcome_r.adjustSize()
        tx = int(self.welcome_bar.width() * 0.05)
        ty = int((self.welcome_bar.height() - self.welcome_l.height()) / 2) - 2
        self.welcome_l.move(tx, ty)
        self.welcome_r.move(tx + self.welcome_l.width(), ty)

        # Sidebar — floats as overlay, content never shifts
        self._dim_overlay.setGeometry(0, 0, w, h)

        if self.sidebar_open:
            sw = self.sidebar_width
            self.sidebar.setGeometry(0, 0, sw, h)
            self.sidebar.show()
            self._dim_overlay.show()
            self._dim_overlay.raise_()
            self.sidebar.raise_()

            th, bh = 170, 120
            mh = h - th - bh
            self.sidebar_top.setGeometry(0, 0, sw, th)
            self.sidebar_mid.setGeometry(0, th, sw, mh)
            self.sidebar_bottom.setGeometry(0, th + mh, sw, bh)
            for f in (self.sidebar_top, self.sidebar_mid, self.sidebar_bottom):
                f.show()

            self.logo_top.setGeometry(88, 18, 160, 160)
            self.btn_toggle.setGeometry(sw - 54, 10, 36, 36)
            self.btn_toggle.raise_()

            by = 26
            self.logo_bottom.setGeometry(18, by, 40, 40)
            self.logo_bottom.show()
            self.bottom_student.setFont(QFont("Poppins", 12, QFont.Bold))
            self.bottom_info.setFont(QFont("Poppins", 9, QFont.Medium))
            self.bottom_student.adjustSize()
            self.bottom_info.adjustSize()
            self.bottom_student.move(66, by + 2)
            self.bottom_info.move(66, by + 18)
            for wgt in (self.logo_bottom, self.bottom_student, self.bottom_info):
                wgt.raise_();  wgt.show()

            bx = 0;  bw = sw;  bh2 = 42;  cy2 = 220;  bg = 7
            for btn in (self.btn_dashboard, self.btn_logout, self.btn_exit):
                btn.setGeometry(bx, cy2, bw, bh2)
                btn.show();  cy2 += bh2 + bg

            self.btn_toggle.setStyleSheet("""
                QPushButton {
                    background:transparent; color:white; border:none;
                    font-size:28px; font-weight:700; font-family:'Poppins';
                }
                QPushButton:hover { color:#ffe7ee; }
            """)
        else:
            self.sidebar.hide()
            self._dim_overlay.hide()
            for btn in (self.btn_dashboard, self.btn_logout, self.btn_exit):
                btn.hide()
            self.btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{RED}; border:none;
                    font-size:28px; font-weight:700; font-family:'Poppins';
                }}
                QPushButton:hover {{ color:{RED_DARK}; }}
            """)

        # Cards
        self.students_card.setGeometry(content_x, card_y, small_w, card_h)
        self.register_card.setGeometry(content_x + small_w + gap, card_y, small_w, card_h)
        self.notify_card.setGeometry(content_x + (small_w + gap) * 2, card_y, small_w, card_h)

        s = int(card_h * 0.40);  sx = int(card_h * 0.18)
        sy = int((card_h - s) / 2);  stx = sx + s + 34
        self.students_card.layout_card(s, 15, 11, sx, sy, stx,
                                       int(card_h * 0.24), int(card_h * 0.62))

        r = int(card_h * 0.40);  rx = int(card_h * 0.18)
        ry = int((card_h - r) / 2);  rtx = rx + r + 28
        self.register_card.layout_card(r, 16, 1, rx, ry, rtx,
                                       int(card_h * 0.18), int(card_h * 0.30))
        self.register_card.subtitle.hide()

        n = int(card_h * 0.34);  nx = int(card_h * 0.10)
        ny = int(card_h * 0.22);  ntx = nx + n + 16
        self.notify_card.layout_card(n, 15, 11, nx, ny, ntx,
                                     int(card_h * 0.22), int(card_h * 0.56))
        self.notify_card.title.setFont(QFont("Poppins", 15, QFont.Bold))
        self.notify_card.title.setStyleSheet(
            f"background:transparent;border:none;color:white;"
            f"font-family:'Poppins';font-weight:700;")
        self.notify_card.title.adjustSize()
        self.notify_card.title.move(ntx, int(card_h * 0.20))
        self.notify_card.subtitle.show()
        self.notify_card.subtitle.setFont(QFont("Poppins", 11, QFont.Medium))
        self.notify_card.subtitle.setStyleSheet(
            f"background:transparent;border:none;color:white;font-family:'Poppins';")
        self.notify_card.subtitle.adjustSize()
        self.notify_card.subtitle.move(ntx, int(card_h * 0.55))

        # Lower panels
        self.calendar_panel.setGeometry(content_x, lower_y, lower_w, lower_h)
        self.graph_panel.setGeometry(content_x + lower_w + gap, lower_y, lower_w, lower_h)

        # Chart fills the graph panel (below its title)
        chart_margin = 44
        self.chart.setGeometry(
            10, chart_margin,
            self.graph_panel.width() - 20,
            self.graph_panel.height() - chart_margin - 10)

        self.prev_month.setGeometry(18, 48, 30, 30)
        self.next_month.setGeometry(self.calendar_panel.width() - 48, 48, 30, 30)

        self.cal_month.setFont(QFont("Poppins", max(11, int(h * 0.017)), QFont.Bold))
        self.cal_month.adjustSize()
        self.cal_month.move(
            (self.calendar_panel.width() - self.cal_month.width()) // 2, 52)

        sx2 = 24;  gt = 92
        cw  = max(42, int(self.calendar_panel.width() * 0.11))
        ch  = 34;  cg = 4;  rg = 8

        for i, lbl in enumerate(self.weekday_labels):
            lbl.setFont(QFont("Poppins", 9, QFont.Medium))
            lbl.adjustSize()
            x = sx2 + i * (cw + cg) + (cw - lbl.width()) // 2
            lbl.move(x, gt)

        dy = gt + 24
        for idx, btn in enumerate(self.day_buttons):
            btn.setGeometry(
                sx2 + (idx % 7) * (cw + cg),
                dy  + (idx // 7) * (ch + rg),
                cw, ch)

        hy = dy + 6 * (ch + rg) + 18
        self.holiday_title.setFont(QFont("Poppins", 11, QFont.Bold))
        self.holiday_title.adjustSize()
        self.holiday_title.move(20, hy)
        self.holiday_date.setFont(QFont("Poppins", 10, QFont.Medium))
        self.holiday_date.adjustSize()
        self.holiday_date.move(20, hy + 24)

        boxy = hy + 50
        self.holiday_box.setGeometry(
            16, boxy,
            self.calendar_panel.width() - 32,
            self.calendar_panel.height() - boxy - 16)
        self.holiday_list.setGeometry(
            8, 8,
            self.holiday_box.width() - 16,
            self.holiday_box.height() - 16)


# ── Standalone dev run ────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DashboardWindow(user={"id": 0, "username": "dev",
                                "role": "admin", "email": ""})
    win.showMaximized()
    sys.exit(app.exec_())