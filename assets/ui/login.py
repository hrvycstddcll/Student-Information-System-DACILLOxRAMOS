import sys
import sqlite3
import hashlib
import json
import os
import time

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFrame, QCheckBox, QDialog, QVBoxLayout, QHBoxLayout,
    QMessageBox
)
from PyQt5.QtGui import (
    QPixmap, QFont, QFontDatabase, QIcon, QPainter, QPen, QColor
)
from PyQt5.QtCore import (
    Qt, QSize, QRect, QTimer, QEvent,
    QPropertyAnimation, QPoint, pyqtSignal
)

# ── Paths (relative to project root, where main.py lives) ────────────────────
_HERE    = os.path.dirname(os.path.abspath(__file__))          # assets/ui/
_ROOT    = os.path.join(_HERE, "..", "..")                     # project root
DB_PATH       = os.path.join(_ROOT, "database","sis_users.db")
REMEMBER_FILE = os.path.join(_ROOT, "database","jsonsremember_me.json")
FONTS_DIR     = os.path.join(_ROOT, "assets", "fonts")
IMAGES_DIR    = os.path.join(_ROOT, "assets", "images")


# ── Helpers ───────────────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Create users table and seed default accounts on first run."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT    UNIQUE NOT NULL,
            password TEXT    NOT NULL,
            role     TEXT    NOT NULL DEFAULT 'student',
            email    TEXT
        )
    """)
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        seeds = [
            ("admin",   hash_password("Admin@123"), "admin",   "admin@school.edu"),
        ]
        c.executemany(
            "INSERT INTO users (username, password, role, email) VALUES (?,?,?,?)",
            seeds
        )
    conn.commit()
    conn.close()


def authenticate(username: str, password: str):
    """Returns user dict on success, None on failure."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, username, role, email FROM users "
        "WHERE username=? AND password=?",
        (username, hash_password(password))
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "role": row[2], "email": row[3]}
    return None


def save_remember(username: str):
    with open(REMEMBER_FILE, "w") as f:
        json.dump({"username": username}, f)


def load_remember() -> str:
    if os.path.exists(REMEMBER_FILE):
        with open(REMEMBER_FILE) as f:
            return json.load(f).get("username", "")
    return ""


def clear_remember():
    if os.path.exists(REMEMBER_FILE):
        os.remove(REMEMBER_FILE)


# ── Custom CheckBox ───────────────────────────────────────────────────────────
class CheckBoxWithTick(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(26 + fm.horizontalAdvance(self.text()) + 6,
                     max(18, fm.height()) + 4)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        red      = QColor("#c62828")
        box_size = 16
        box_y    = (self.height() - box_size) // 2
        box_rect = QRect(0, box_y, box_size, box_size)

        painter.setPen(QPen(red, 1.2))
        painter.setBrush(Qt.white)
        painter.drawRoundedRect(box_rect, 4, 4)

        if self.isChecked():
            painter.setPen(QPen(red, 2))
            painter.drawLine(4, box_y + 8,  7, box_y + 11)
            painter.drawLine(7, box_y + 11, 12, box_y + 5)

        painter.setPen(red)
        painter.setFont(self.font())
        painter.drawText(
            QRect(24, 0, self.width() - 24, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text()
        )


# ── Forgot Password Dialog ────────────────────────────────────────────────────
class ForgotPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Forgot Password")
        self.setFixedSize(420, 260)
        self.setStyleSheet("""
            QDialog    { background: white; }
            QLabel     { color: #c62828; font-family: Poppins; }
            QLineEdit  {
                border: 1px solid #e7a6ad; border-radius: 8px;
                padding: 8px 14px; color: #c62828;
                font-family: Poppins; font-size: 11pt;
            }
            QLineEdit:focus { border: 1.5px solid #c62828; }
            QPushButton {
                background: #b90d33; color: white;
                border: none; border-radius: 8px;
                padding: 10px; font-family: Poppins; font-size: 11pt;
            }
            QPushButton:hover   { background: #d3133d; }
            QPushButton:pressed { background: #990a2a; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(14)

        title = QLabel("Reset Password")
        title.setFont(QFont("Poppins", 14))
        layout.addWidget(title)

        self.username_edit = QLineEdit(placeholderText="Enter your username")
        self.new_pass_edit = QLineEdit(
            placeholderText="New password",
            echoMode=QLineEdit.Password
        )
        layout.addWidget(self.username_edit)
        layout.addWidget(self.new_pass_edit)

        btn_row   = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
            QPushButton       { background:#e7a6ad; color:#c62828; }
            QPushButton:hover { background:#d38a92; }
        """)
        cancel_btn.clicked.connect(self.reject)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._do_reset)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_lbl)

    def _do_reset(self):
        username = self.username_edit.text().strip()
        new_pass = self.new_pass_edit.text()
        if not username or not new_pass:
            self.status_lbl.setText("Please fill in both fields.")
            return
        if len(new_pass) < 6:
            self.status_lbl.setText("Password must be at least 6 characters.")
            return
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if not c.fetchone():
            conn.close()
            self.status_lbl.setText("Username not found.")
            return
        c.execute(
            "UPDATE users SET password=? WHERE username=?",
            (hash_password(new_pass), username)
        )
        conn.commit()
        conn.close()
        self.status_lbl.setStyleSheet("color: green;")
        self.status_lbl.setText("Password updated! You may now log in.")
        QTimer.singleShot(1500, self.accept)


# ── Login Window ──────────────────────────────────────────────────────────────
class LoginWindow(QWidget):
    # Emitted with the user dict when authentication succeeds.
    # ApplicationManager connects to this to open the dashboard.
    login_successful = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Student Information System")
        self.setMinimumSize(1000, 700)

        # Load fonts (look in assets/fonts/ first, then root)
        for fname in ("LeagueSpartan-VariableFont_wght.ttf", "Poppins-Regular.ttf"):
            for search in (os.path.join(FONTS_DIR, fname), fname):
                if os.path.exists(search):
                    QFontDatabase.addApplicationFont(search)
                    break

        self.password_visible  = False
        self._login_attempts   = 0
        self._locked_until     = 0.0   # epoch seconds; 0 = not locked
        self._shake_anims      = []
        self._lock_timer       = None

        init_db()
        self._build_ui()

        # Pre-fill remembered username
        saved = load_remember()
        if saved:
            self.username.setText(saved)
            self.remember.setChecked(True)

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        self.bg = QLabel(self)
        bg_path = os.path.join(IMAGES_DIR, "GUI.png")
        self.bg.setPixmap(QPixmap(bg_path))
        self.bg.setScaledContents(True)
        self.bg.setGeometry(self.rect())

        self.user_label = QLabel("Username", self)
        self.user_label.setStyleSheet("color:#c62828;")

        self.username = QLineEdit(self)
        self.username.setStyleSheet(self._field_css())
        self.username.returnPressed.connect(self.password.setFocus
                                            if hasattr(self, "password")
                                            else lambda: None)

        self.pass_label = QLabel("Password", self)
        self.pass_label.setStyleSheet("color:#c62828;")

        self.password = QLineEdit(self)
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setStyleSheet(self._field_css(right_pad=72))
        self.password.returnPressed.connect(self._attempt_login)

        # Wire username Enter → focus password (now that self.password exists)
        self.username.returnPressed.connect(self.password.setFocus)

        self.eye_divider = QFrame(self)
        self.eye_divider.setStyleSheet("background:#e7a6ad; border:none;")

        self.eye = QPushButton(self)
        self.eye.setCursor(Qt.PointingHandCursor)
        self.eye.setFlat(True)
        self.eye.setStyleSheet(
            "QPushButton{border:none;background:transparent;"
            "padding:0;min-width:24px;min-height:24px;}"
        )
        eye_icon = os.path.join(IMAGES_DIR, "eye.png")
        if not os.path.exists(eye_icon):
            eye_icon = "eye.png"   # fallback
        self.eye.setIcon(QIcon(eye_icon))
        self.eye.clicked.connect(self._toggle_password)

        self.error_label = QLabel("", self)
        self.error_label.setStyleSheet("color:#c62828;background:transparent;")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()

        self.remember = CheckBoxWithTick("Remember me", self)

        self.forgot = QLabel("Forgot Password", self)
        self.forgot.setStyleSheet("color:#c62828;text-decoration:underline;")
        self.forgot.setCursor(Qt.PointingHandCursor)
        self.forgot.mousePressEvent = lambda _: self._open_forgot()

        self.login_btn = QPushButton("Login", self)
        self.login_btn.setCursor(Qt.PointingHandCursor)
        self.login_btn.setStyleSheet("""
            QPushButton          { background:#b90d33;color:white;
                                   border:none;border-radius:8px; }
            QPushButton:hover    { background:#d3133d; }
            QPushButton:pressed  { background:#990a2a; }
            QPushButton:disabled { background:#e7a6ad;color:#fff; }
        """)
        self.login_btn.clicked.connect(self._attempt_login)

        self._update_positions()

    @staticmethod
    def _field_css(right_pad: int = 0) -> str:
        pr = 14 + right_pad
        return (
            f"QLineEdit{{border:1px solid #e7a6ad;border-radius:8px;"
            f"padding-left:14px;padding-right:{pr}px;"
            f"background:transparent;color:#c62828;}}"
            f"QLineEdit:focus{{border:1.5px solid #c62828;}}"
        )

    # ── Authentication ────────────────────────────────────────────────────────
    def _attempt_login(self):
        # Lockout guard
        if self._locked_until and time.time() < self._locked_until:
            remaining = int(self._locked_until - time.time())
            self._show_error(f"Too many attempts. Try again in {remaining}s.")
            return

        username = self.username.text().strip()
        password = self.password.text()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            self._shake_form()
            return

        user = authenticate(username, password)

        if user:
            # ── SUCCESS ──
            self._login_attempts = 0
            self._locked_until   = 0.0
            self.error_label.hide()

            if self.remember.isChecked():
                save_remember(username)
            else:
                clear_remember()

            # Signal ApplicationManager — it will open the dashboard
            self.login_successful.emit(user)

        else:
            # ── FAILURE ──
            self._login_attempts += 1
            if self._login_attempts >= 5:
                self._locked_until = time.time() + 30
                self._login_attempts = 0
                self._show_error("Too many failed attempts. Locked for 30 seconds.")
                if self._lock_timer is None:
                    self._lock_timer = QTimer(self)
                    self._lock_timer.timeout.connect(self._tick_lockout)
                self._lock_timer.start(1000)
            else:
                left = 5 - self._login_attempts
                self._show_error(
                    f"Invalid username or password. "
                    f"({left} attempt{'s' if left != 1 else ''} left)"
                )
            self._shake_form()

    def _tick_lockout(self):
        remaining = int(self._locked_until - time.time())
        if remaining <= 0:
            self._lock_timer.stop()
            self.error_label.hide()
        else:
            self._show_error(f"Too many attempts. Try again in {remaining}s.")

    # ── UI helpers ────────────────────────────────────────────────────────────
    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.show()

    def _shake_form(self):
        """Shake every form widget horizontally in unison."""
        targets = [
            self.user_label, self.username,
            self.pass_label, self.password,
            self.eye_divider, self.eye,
            self.remember, self.forgot,
            self.login_btn, self.error_label,
        ]
        offsets = [0, -10, 10, -8, 8, -5, 5, -2, 2, 0]
        steps   = [i / (len(offsets) - 1) for i in range(len(offsets))]

        self._shake_anims.clear()
        for widget in targets:
            orig = widget.pos()
            anim = QPropertyAnimation(widget, b"pos", self)
            anim.setDuration(380)
            for t, dx in zip(steps, offsets):
                anim.setKeyValueAt(t, QPoint(orig.x() + dx, orig.y()))
            anim.start(QPropertyAnimation.DeleteWhenStopped)
            self._shake_anims.append(anim)

    def _toggle_password(self):
        self.password_visible = not self.password_visible
        self.password.setEchoMode(
            QLineEdit.Normal if self.password_visible else QLineEdit.Password
        )

    def _open_forgot(self):
        ForgotPasswordDialog(self).exec_()

    # ── Layout ────────────────────────────────────────────────────────────────
    def _is_maximized(self):
        return self.isMaximized()

    def _update_positions(self):
        if not hasattr(self, "bg"):
            return
        self.bg.setGeometry(self.rect())
        w, h = self.width(), self.height()

        if not self._is_maximized():
            form_x, form_y, form_w, inp_h = 138, 278, 405, 50
            pass_gap, opts_gap, btn_gap, btn_h = 96, 98, 46, 50
            lbl_f, inp_f, opt_f, btn_f = 11, 11, 10, 13
            div_xpad, div_tp, div_bp = 42, 10, 10
            eye_sz, eye_ico, eye_xoff = 28, 18, 8
        else:
            form_x = int(w * 0.13)
            form_y = int(h * 0.41)
            form_w = int(w * 0.32)
            inp_h  = 58
            pass_gap, opts_gap, btn_gap, btn_h = 112, 114, 52, 58
            lbl_f, inp_f, opt_f, btn_f = 12, 12, 11, 14
            div_xpad, div_tp, div_bp = 52, 10, 10
            eye_sz, eye_ico, eye_xoff = 40, 26, 6

        lg = 10   # label→input gap

        for wgt, sz in [
            (self.user_label,  lbl_f),
            (self.pass_label,  lbl_f),
            (self.username,    inp_f),
            (self.password,    inp_f),
            (self.remember,    opt_f),
            (self.forgot,      opt_f),
            (self.login_btn,   btn_f),
            (self.error_label, opt_f - 1),
        ]:
            wgt.setFont(QFont("Poppins", sz))

        self.user_label.adjustSize()
        self.pass_label.adjustSize()
        self.forgot.adjustSize()
        self.remember.resize(self.remember.sizeHint())

        # Username
        self.user_label.move(form_x, form_y)
        ubox_y = form_y + lg + 18
        self.username.setGeometry(form_x, ubox_y, form_w, inp_h)

        # Password
        pass_y = form_y + pass_gap
        self.pass_label.move(form_x, pass_y)
        pbox_y = pass_y + lg + 18
        self.password.setGeometry(form_x, pbox_y, form_w, inp_h)

        # Eye divider + button
        div_x = form_x + form_w - div_xpad
        self.eye_divider.setGeometry(
            div_x, pbox_y + div_tp,
            1, inp_h - div_tp - div_bp
        )
        self.eye.setIconSize(QSize(eye_ico, eye_ico))
        self.eye.setGeometry(
            div_x + eye_xoff,
            pbox_y + (inp_h - eye_sz) // 2,
            eye_sz, eye_sz
        )

        # Options row
        opts_y = pass_y + opts_gap
        self.remember.move(form_x, opts_y)
        self.forgot.move(form_x + form_w - self.forgot.width(), opts_y + 1)

        # Login button + error label
        btn_y = opts_y + btn_gap
        self.login_btn.setGeometry(form_x, btn_y, form_w, btn_h)
        self.error_label.setGeometry(form_x, btn_y + btn_h + 6, form_w, 22)

        self.eye.raise_()
        self.eye_divider.raise_()

    # ── Qt events ─────────────────────────────────────────────────────────────
    def resizeEvent(self, event):
        self._update_positions()
        super().resizeEvent(event)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and hasattr(self, "bg"):
            QTimer.singleShot(0, self._update_positions)
        super().changeEvent(event)


# ── Standalone run (dev only) ─────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LoginWindow()
    win.login_successful.connect(
        lambda u: (print("Logged in:", u), win.close())
    )
    win.showMaximized()
    sys.exit(app.exec_())