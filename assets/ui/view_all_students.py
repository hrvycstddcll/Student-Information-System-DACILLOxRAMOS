import sys
import os
import sqlite3
from datetime import datetime

from assets.ui.add_student import RegisterStudentWindow
# No changes to imports; standard PyQt5 components used for the new UI
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QFrame,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMenu,
    QMessageBox,
    QDialog,
    QScrollArea,
    QSizePolicy,
)

RED = "#b90d33"
RED_DARK = "#990a2a"
RED_BORDER = "#e7bcc5"
BG = "#f7f7f9"
CARD = "#ffffff"
TEXT = "#3f3f46"
MUTED = "#7a7a7a"
HEADER_BG = "#fff5f7"
ROW_HOVER = "#fff8fa"

DEPARTMENTS = ["CABEIHM", "CAS", "CCJE", "CHS", "CICS", "CTE"]
STATUS_OPTIONS = ["Regular", "Irregular", "Transferee"]

# ── Database paths ────────────────────────────────────────────────────────────
_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DB_PATH = os.path.join(_BASE, "database", "sis_users.db")
BAK_PATH = os.path.join(_BASE, "database", "deleted_students.db")


def _conn(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def _ensure_backup_table():
    with _conn(BAK_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS deleted_students (
                deleted_at       TEXT NOT NULL,
                id               TEXT,
                first_name       TEXT,
                middle_name      TEXT,
                last_name        TEXT,
                suffix           TEXT,
                age              INTEGER,
                gender           TEXT,
                department       TEXT,
                status           TEXT,
                year_level       TEXT,
                contact          TEXT,
                email            TEXT,
                guardian_name    TEXT,
                guardian_contact TEXT,
                address          TEXT
            )
        """)
        c.commit()


def fetch_all_students() -> list:
    try:
        with _conn(DB_PATH) as c:
            rows = c.execute("""
                SELECT id,
                       first_name || ' ' ||
                       CASE WHEN middle_name != '' AND middle_name IS NOT NULL
                            THEN middle_name || ' ' ELSE '' END ||
                       last_name AS name,
                       gender, age, department, status,
                       first_name, middle_name, last_name,
                       suffix, year_level, contact, email,
                       guardian_name, guardian_contact, address
                FROM students
                ORDER BY last_name, first_name
            """).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


# ── Archive Logic ─────────────────────────────────────────────────────────────

def fetch_deleted_students() -> list:
    """Fetches records from the backup database."""
    try:
        if not os.path.exists(BAK_PATH): return []
        with _conn(BAK_PATH) as c:
            rows = c.execute("SELECT * FROM deleted_students ORDER BY deleted_at DESC").fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def restore_student_record(student: dict):
    """Moves a student from deleted_students.db back to sis_users.db."""
    data = student.copy()
    data.pop('deleted_at', None)

    with _conn(DB_PATH) as mc:
        # Prevent restoring an ID that was already taken since deletion
        exists = mc.execute("SELECT 1 FROM students WHERE id = ?", (data['id'],)).fetchone()
        if exists:
            raise sqlite3.IntegrityError(f"Student ID {data['id']} is already active.")

        mc.execute("""
            INSERT INTO students (id, first_name, middle_name, last_name, suffix, age, 
                                gender, department, status, year_level, contact, 
                                email, guardian_name, guardian_contact, address)
            VALUES (:id, :first_name, :middle_name, :last_name, :suffix, :age, 
                    :gender, :department, :status, :year_level, :contact, 
                    :email, :guardian_name, :guardian_contact, :address)
        """, data)
        mc.commit()

    with _conn(BAK_PATH) as bc:
        bc.execute("DELETE FROM deleted_students WHERE id = ? AND deleted_at = ?",
                   (student['id'], student['deleted_at']))
        bc.commit()


def bulk_restore_students(students: list):
    """Restores multiple students in a batch."""
    errors = []
    for s in students:
        try:
            restore_student_record(s)
        except sqlite3.IntegrityError as e:
            errors.append(str(e))
    if errors:
        raise Exception("\n".join(errors))


def student_id_exists(new_id: str, exclude_id: str = None) -> bool:
    """Check if student ID exists, optionally excluding the current record."""
    with _conn(DB_PATH) as c:
        if exclude_id:
            row = c.execute(
                "SELECT 1 FROM students WHERE id = ? AND id != ?",
                (new_id, exclude_id)
            ).fetchone()
        else:
            row = c.execute(
                "SELECT 1 FROM students WHERE id = ?", (new_id,)
            ).fetchone()
    return row is not None


def update_student(data: dict):
    """Update student. If the ID changed, rename the primary key safely."""
    old_id = data.get("_old_id") or data["id"]
    with _conn(DB_PATH) as c:
        if old_id != data["id"]:
            # Rename PK: insert new row, delete old
            c.execute("""
                INSERT INTO students
                SELECT
                    :id, :first_name, :middle_name, :last_name, :suffix,
                    :age, :gender, :department, :status, :year_level,
                    :contact, :email, :guardian_name, :guardian_contact,
                    :address
            """, data)
            c.execute("DELETE FROM students WHERE id = ?", (old_id,))
        else:
            c.execute("""
                UPDATE students SET
                    first_name=:first_name,     middle_name=:middle_name,
                    last_name=:last_name,        suffix=:suffix,
                    age=:age,                    gender=:gender,
                    department=:department,      status=:status,
                    year_level=:year_level,      contact=:contact,
                    email=:email,                guardian_name=:guardian_name,
                    guardian_contact=:guardian_contact, address=:address
                WHERE id=:id
            """, data)
        c.commit()


def delete_and_backup(student: dict):
    """Copy student to backup DB then remove from main DB."""
    _ensure_backup_table()
    record = {k: student.get(k) for k in (
        "id", "first_name", "middle_name", "last_name", "suffix",
        "age", "gender", "department", "status", "year_level",
        "contact", "email", "guardian_name", "guardian_contact", "address"
    )}
    record["deleted_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn(BAK_PATH) as bc:
        bc.execute("""
            INSERT INTO deleted_students VALUES (
                :deleted_at, :id, :first_name, :middle_name, :last_name,
                :suffix, :age, :gender, :department, :status,
                :year_level, :contact, :email,
                :guardian_name, :guardian_contact, :address
            )
        """, record)
        bc.commit()
    with _conn(DB_PATH) as mc:
        mc.execute("DELETE FROM students WHERE id = ?", (student["id"],))
        mc.commit()


def bulk_delete_and_backup(students: list):
    """Backup and delete multiple students in one transaction each."""
    _ensure_backup_table()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn(BAK_PATH) as bc:
        for s in students:
            record = {k: s.get(k) for k in (
                "id", "first_name", "middle_name", "last_name", "suffix",
                "age", "gender", "department", "status", "year_level",
                "contact", "email", "guardian_name", "guardian_contact",
                "address"
            )}
            record["deleted_at"] = ts
            bc.execute("""
                INSERT INTO deleted_students VALUES (
                    :deleted_at, :id, :first_name, :middle_name, :last_name,
                    :suffix, :age, :gender, :department, :status,
                    :year_level, :contact, :email,
                    :guardian_name, :guardian_contact, :address
                )
            """, record)
        bc.commit()
    ids = [s["id"] for s in students]
    with _conn(DB_PATH) as mc:
        mc.executemany("DELETE FROM students WHERE id = ?",
                       [(i,) for i in ids])
        mc.commit()


# ── Archives dialog ───────────────────────────────────────────────────────────
class ArchivesWindow(QDialog):
    """Window to view and batch restore deleted students."""
    restored = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deleted Students Archive")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"background:{BG};")
        self._select_mode = False
        self.deleted_students = []
        self._build()
        self._load_data()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)

        header_row = QHBoxLayout()
        header = QLabel("Archived Students")
        header.setFont(QFont("Poppins", 22, QFont.Bold))
        header.setStyleSheet(f"color:{RED};")
        header_row.addWidget(header)
        header_row.addStretch()

        # Batch Restore Controls
        self.batch_btn = QPushButton("☑  Batch Restore")
        self.batch_btn.setFixedSize(160, 40)
        self.batch_btn.setCursor(Qt.PointingHandCursor)
        self.batch_btn.setStyleSheet(
            f"QPushButton {{ background:{RED}; color:white; border:1.5px solid white; border-radius:10px; font-weight:bold; }} QPushButton:hover {{ background:{RED_DARK}; }}")
        self.batch_btn.clicked.connect(self._toggle_batch_mode)
        header_row.addWidget(self.batch_btn)

        self.confirm_restore_btn = QPushButton("Restore Selected")
        self.confirm_restore_btn.setFixedSize(160, 40)
        self.confirm_restore_btn.setStyleSheet(
            f"QPushButton {{ background:{RED}; color:white; border-radius:10px; font-weight:bold; }}")
        self.confirm_restore_btn.clicked.connect(self._handle_batch_restore)
        self.confirm_restore_btn.hide()
        header_row.addWidget(self.confirm_restore_btn)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(110, 40)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            f"QPushButton {{ background:white; color:{MUTED}; border:1.5px solid #ccc; border-radius:10px; font-weight:bold; }} QPushButton:hover {{ background:#f5f5f5; }}")
        close_btn.clicked.connect(self.reject)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        self.table_card = QFrame()
        self.table_card.setStyleSheet(f"background:{CARD}; border:1px solid {RED_BORDER}; border-radius:20px;")
        table_layout = QVBoxLayout(self.table_card)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["", "DELETED AT", "ID", "STUDENT NAME", "DEPARTMENT", "ACTION"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setStyleSheet(f"""
            QTableWidget {{ background:white; border:none; border-radius:15px; color:{TEXT}; font-family:'Poppins'; }}
            QHeaderView::section {{ background:{HEADER_BG}; color:{RED}; padding:15px; font-weight:bold; border:none; border-bottom:1px solid #f0cad3; }}
            QTableWidget::item {{ border-bottom:1px solid #f4dde3; padding:15px; }}
            QTableWidget::item:hover {{ background:{ROW_HOVER}; }}
        """)

        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        h.setSectionResizeMode(1, QHeaderView.Fixed)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 0)  # Initially hidden
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 150)

        table_layout.addWidget(self.table)
        layout.addWidget(self.table_card)

    def _load_data(self):
        self.deleted_students = fetch_deleted_students()
        self.table.setRowCount(len(self.deleted_students))
        for i, s in enumerate(self.deleted_students):
            self.table.setRowHeight(i, 65)

            # Checkbox for batch
            cb_wrap = QWidget();
            cb_lay = QHBoxLayout(cb_wrap)
            cb = QCheckBox();
            cb.setFixedSize(20, 20)
            cb_lay.setContentsMargins(0, 0, 0, 0);
            cb_lay.setAlignment(Qt.AlignCenter);
            cb_lay.addWidget(cb)
            self.table.setCellWidget(i, 0, cb_wrap)

            self.table.setItem(i, 1, QTableWidgetItem(s['deleted_at']))
            self.table.setItem(i, 2, QTableWidgetItem(s['id']))
            self.table.setItem(i, 3, QTableWidgetItem(f"{s['first_name']} {s['last_name']}"))
            self.table.setItem(i, 4, QTableWidgetItem(s['department']))

            btn = QPushButton("Restore")
            btn.setFixedSize(100, 36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background:{RED}; color:white; border-radius:8px; font-weight:bold; }} QPushButton:hover {{ background:{RED_DARK}; }}")
            btn.clicked.connect(lambda _, d=s: self._handle_restore(d))

            w = QWidget();
            l = QHBoxLayout(w)
            l.setContentsMargins(0, 0, 0, 0);
            l.setAlignment(Qt.AlignCenter);
            l.addWidget(btn)
            self.table.setCellWidget(i, 5, w)

    def _toggle_batch_mode(self):
        self._select_mode = not self._select_mode
        self.table.setColumnWidth(0, 50 if self._select_mode else 0)
        self.confirm_restore_btn.setVisible(self._select_mode)
        self.batch_btn.setText("Cancel Batch" if self._select_mode else "☑  Batch Restore")

    def _handle_restore(self, student):
        try:
            restore_student_record(student)
            QMessageBox.information(self, "Success", f"Restored {student['first_name']} {student['last_name']}")
            self.restored.emit()
            self._load_data()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _handle_batch_restore(self):
        selected = []
        for row in range(self.table.rowCount()):
            cb = self.table.cellWidget(row, 0).findChild(QCheckBox)
            if cb and cb.isChecked():
                selected.append(self.deleted_students[row])

        if not selected:
            QMessageBox.warning(self, "Selection", "Please select students to restore.")
            return

        try:
            bulk_restore_students(selected)
            QMessageBox.information(self, "Success", f"Restored {len(selected)} records.")
            self.restored.emit()
            self._toggle_batch_mode()
            self._load_data()
        except Exception as e:
            QMessageBox.critical(self, "Batch Error", str(e))


# ── Edit dialog ───────────────────────────────────────────────────────────────
class EditStudentDialog(QDialog):
    saved = pyqtSignal()

    def __init__(self, student: dict, parent=None):
        super().__init__(parent)
        self.student = student  # original data
        self._old_id = student["id"]  # remember original ID
        self.setWindowTitle("Edit Student")
        self.setMinimumWidth(860)
        self.setStyleSheet(f"background:{BG};")
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("Edit Student Information")
        title.setFont(QFont("Poppins", 16, QFont.Bold))
        title.setStyleSheet(
            f"color:{RED}; background:transparent; border:none;")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background:transparent; border:none;")

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background:{CARD};
                border:1px solid {RED_BORDER};
                border-radius:16px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        self.f_id = self._input("Student ID")
        self.f_fname = self._input("First name")
        self.f_mname = self._input("Middle name")
        self.f_lname = self._input("Last name")
        self.f_suffix = self._input("Suffix")
        self.f_age = self._input("Age")
        self.f_gender = self._combo(["Male", "Female", "Other"])
        self.f_dept = self._combo(DEPARTMENTS)
        self.f_status = self._combo(STATUS_OPTIONS)
        self.f_year = self._combo(
            ["1st Year", "2nd Year", "3rd Year", "4th Year"])
        self.f_contact = self._input("Contact number")
        self.f_email = self._input("Email address")
        self.f_gname = self._input("Guardian name")
        self.f_gcontact = self._input("Guardian contact")
        self.f_address = self._input("Address")

        # ID is now EDITABLE — but we warn on duplicate
        self.f_id.setToolTip(
            "You may change the Student ID. "
            "A warning will appear if the new ID already exists.")
        self.f_id.editingFinished.connect(self._check_id_conflict)

        # ID field hint label
        self.id_hint = QLabel("")
        self.id_hint.setFont(QFont("Poppins", 8))
        self.id_hint.setStyleSheet(
            f"color:{RED}; background:transparent; border:none;")

        id_wrap = QWidget()
        id_wrap.setStyleSheet("background:transparent; border:none;")
        id_lay = QVBoxLayout(id_wrap)
        id_lay.setContentsMargins(0, 0, 0, 0)
        id_lay.setSpacing(3)
        id_lbl = QLabel("Student ID")
        id_lbl.setFont(QFont("Poppins", 9, QFont.Bold))
        id_lbl.setStyleSheet(
            f"color:{TEXT}; background:transparent; border:none;")
        id_lay.addWidget(id_lbl)
        id_lay.addWidget(self.f_id)
        id_lay.addWidget(self.id_hint)

        grid.addWidget(id_wrap, 0, 0)
        grid.addWidget(self._field("Age *", self.f_age), 0, 1)
        grid.addWidget(self._field("Gender *", self.f_gender), 0, 2)
        grid.addWidget(self._field("First Name *", self.f_fname), 1, 0)
        grid.addWidget(self._field("Middle Name", self.f_mname), 1, 1)
        grid.addWidget(self._field("Last Name *", self.f_lname), 1, 2)
        grid.addWidget(self._field("Suffix", self.f_suffix), 2, 0)
        grid.addWidget(self._field("Department *", self.f_dept), 2, 1)
        grid.addWidget(self._field("Status *", self.f_status), 2, 2)
        grid.addWidget(self._field("Year Level", self.f_year), 3, 0)
        grid.addWidget(self._field("Contact", self.f_contact), 3, 1)
        grid.addWidget(self._field("Email", self.f_email), 3, 2)
        grid.addWidget(self._field("Guardian Name", self.f_gname), 4, 0)
        grid.addWidget(self._field("Guardian Contact", self.f_gcontact), 4, 1)
        grid.addWidget(self._field("Address", self.f_address), 4, 2)

        card_layout.addLayout(grid)

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(card, 0, Qt.AlignTop)
        scroll.setWidget(container)
        root.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(110, 42)
        cancel_btn.setFont(QFont("Poppins", 10, QFont.Bold))
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background:white; color:{RED};
                border:1.5px solid {RED}; border-radius:10px;
            }}
            QPushButton:hover {{ background:#fff5f7; }}
        """)
        cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setFixedSize(150, 42)
        self.save_btn.setFont(QFont("Poppins", 10, QFont.Bold))
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background:{RED}; color:white;
                border:none; border-radius:10px;
            }}
            QPushButton:hover {{ background:{RED_DARK}; }}
        """)
        self.save_btn.clicked.connect(self._save)

        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(self.save_btn)
        root.addLayout(btn_row)

    # ── widget factories ──────────────────────────────────────────────────────
    def _input(self, placeholder):
        w = QLineEdit()
        w.setPlaceholderText(placeholder)
        w.setFixedHeight(42)
        w.setFont(QFont("Poppins", 10))
        w.setStyleSheet(f"""
            QLineEdit {{
                background:white; border:1.5px solid {RED_BORDER};
                border-radius:10px; padding:0 12px; color:{TEXT};
            }}
            QLineEdit:focus {{ border:1.5px solid {RED}; }}
        """)
        return w

    def _combo(self, items):
        w = QComboBox()
        w.addItems(items)
        w.setFixedHeight(42)
        w.setFont(QFont("Poppins", 10))
        w.setCursor(Qt.PointingHandCursor)
        w.setStyleSheet(f"""
            QComboBox {{
                background:white; border:1.5 solid {RED_BORDER};
                border-radius:10px; padding:0 12px; color:{TEXT};
            }}
            QComboBox:hover {{ border:1.5px solid {RED}; }}
            QComboBox::drop-down {{ border:none; width:26px; }}
            QComboBox QAbstractItemView {{
                background:white; border:1px solid {RED_BORDER};
                selection-background-color:#fdf0f3;
                selection-color:{RED}; color:{TEXT};
            }}
        """)
        return w

    def _field(self, label_text, widget):
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent; border:none;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Poppins", 9, QFont.Bold))
        lbl.setStyleSheet(
            f"color:{TEXT}; background:transparent; border:none;")
        lay.addWidget(lbl)
        lay.addWidget(widget)
        return wrap

    def _set_combo(self, combo, value):
        idx = combo.findText(str(value), Qt.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    # ── ID conflict check ─────────────────────────────────────────────────────
    def _check_id_conflict(self):
        new_id = self.f_id.text().strip()
        if not new_id or new_id == self._old_id:
            self.id_hint.setText("")
            self.save_btn.setEnabled(True)
            return
        if student_id_exists(new_id, exclude_id=self._old_id):
            self.id_hint.setText(
                f"⚠  ID '{new_id}' is already in use by another student.")
            self.save_btn.setEnabled(False)
        else:
            self.id_hint.setText("✓  ID is available.")
            self.id_hint.setStyleSheet(
                "color:#2e7d32; background:transparent; border:none;")
            self.save_btn.setEnabled(True)

    # ── load / save ───────────────────────────────────────────────────────────
    def _load(self):
        s = self.student
        self.f_id.setText(str(s.get("id", "")))
        self.f_fname.setText(str(s.get("first_name", "")))
        self.f_mname.setText(str(s.get("middle_name") or ""))
        self.f_lname.setText(str(s.get("last_name", "")))
        self.f_suffix.setText(str(s.get("suffix") or ""))
        self.f_age.setText(str(s.get("age", "")))
        self.f_contact.setText(str(s.get("contact") or ""))
        self.f_email.setText(str(s.get("email") or ""))
        self.f_gname.setText(str(s.get("guardian_name") or ""))
        self.f_gcontact.setText(str(s.get("guardian_contact") or ""))
        self.f_address.setText(str(s.get("address") or ""))
        self._set_combo(self.f_gender, s.get("gender", ""))
        self._set_combo(self.f_dept, s.get("department", ""))
        self._set_combo(self.f_status, s.get("status", ""))
        self._set_combo(self.f_year, s.get("year_level", ""))

    def _save(self):
        new_id = self.f_id.text().strip()
        first = self.f_fname.text().strip()
        last = self.f_lname.text().strip()
        age = self.f_age.text().strip()

        if not new_id or not first or not last or not age:
            QMessageBox.warning(self, "Incomplete",
                                "Student ID, First Name, Last Name and Age are required.")
            return
        if not age.isdigit():
            QMessageBox.warning(self, "Invalid Age",
                                "Age must be a number.")
            return
        # Final duplicate guard (in case user didn't tab out of ID field)
        if new_id != self._old_id and \
                student_id_exists(new_id, exclude_id=self._old_id):
            QMessageBox.warning(self, "Duplicate ID",
                                f"Student ID '{new_id}' is already in use.\n"
                                "Please choose a different ID.")
            return

        data = {
            "_old_id": self._old_id,
            "id": new_id,
            "first_name": first,
            "middle_name": self.f_mname.text().strip(),
            "last_name": last,
            "suffix": self.f_suffix.text().strip(),
            "age": int(age),
            "gender": self.f_gender.currentText(),
            "department": self.f_dept.currentText(),
            "status": self.f_status.currentText(),
            "year_level": self.f_year.currentText(),
            "contact": self.f_contact.text().strip(),
            "email": self.f_email.text().strip(),
            "guardian_name": self.f_gname.text().strip(),
            "guardian_contact": self.f_gcontact.text().strip(),
            "address": self.f_address.text().strip(),
        }
        try:
            update_student(data)
            self.saved.emit()
            QMessageBox.information(self, "Saved",
                                    f"{first} {last}'s record has been updated.")
            self.accept()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error",
                                 f"Failed to save changes:\n{e}")


# ── Action button (per-row ⋯ menu) ────────────────────────────────────────────
class ActionButton(QPushButton):
    def __init__(self, row_data: dict, refresh_callback, parent=None):
        super().__init__("⋯", parent)
        self.row_data = row_data
        self.refresh_callback = refresh_callback
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 42)
        self.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                border-radius:21px; color:{TEXT};
                font-size:22px; font-weight:700;
            }}
            QPushButton:hover {{ background:#f9e8ed; color:{RED}; }}
        """)
        self.clicked.connect(self.show_menu)

    def show_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background:white; border:1px solid {RED_BORDER};
                border-radius:10px; padding:8px;
            }}
            QMenu::item {{
                padding:10px 18px; border-radius:8px;
                color:{TEXT}; font-family:'Poppins'; font-size:12px;
            }}
            QMenu::item:selected {{ background:#fdf0f3; color:{RED}; }}
        """)
        edit_action = menu.addAction("✏  Edit")
        delete_action = menu.addAction("🗑  Delete")
        action = menu.exec_(self.mapToGlobal(QPoint(0, self.height())))
        if action == edit_action:
            self._open_edit()
        elif action == delete_action:
            self._confirm_delete()

    def _open_edit(self):
        dlg = EditStudentDialog(self.row_data, parent=self.window())
        dlg.saved.connect(self.refresh_callback)
        dlg.exec_()

    def _confirm_delete(self):
        name = self.row_data.get("name", "Student")

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Action")
        msg.setIcon(QMessageBox.Question)

        # Simple, centered formal text
        msg.setText(f"<b>Archive record for {name}?</b>")
        msg.setInformativeText("This will move the student to the backup database.")

        # Create buttons
        archive_btn = msg.addButton("Archive", QMessageBox.AcceptRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)

        # Minimal, formal button design (no extra padding or rounded corners)
        archive_btn.setCursor(Qt.PointingHandCursor)
        archive_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {RED};
                color: white;
                padding: 6px 20px;
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{ background-color: {RED_DARK}; }}
        """)

        cancel_btn.setStyleSheet("padding: 6px 20px;")

        msg.exec_()

        if msg.clickedButton() == archive_btn:
            try:
                delete_and_backup(self.row_data)
                self.refresh_callback()
                QMessageBox.information(self, "Success", "Record successfully archived.")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error", f"Operation failed: {e}")


# ── Main window ───────────────────────────────────────────────────────────────
class ViewAllStudentsWindow(QWidget):
    # Column indices
    COL_CHECK = 0
    COL_ID = 1
    COL_NAME = 2
    COL_GENDER = 3
    COL_AGE = 4
    COL_DEPT = 5
    COL_STATUS = 6
    COL_ACTION = 7
    COL_COUNT = 8

    def __init__(self):
        super().__init__()
        self.all_students = []
        self.filtered_students = []
        self._select_mode = False  # checkbox column visible

        self.setWindowTitle("View All Students")
        self.setMinimumSize(1420, 820)
        self.setStyleSheet(f"background:{BG};")
        self.init_ui()
        self.refresh_table()

    # ── UI ────────────────────────────────────────────────────────────────────
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 26, 28, 26)
        main_layout.setSpacing(18)

        # Title row
        title_row = QHBoxLayout()
        self.title_label = QLabel("View All Students")
        self.title_label.setFont(QFont("Poppins", 24, QFont.Bold))
        self.title_label.setStyleSheet(f"color:{RED}; background:transparent;")

        # Select / bulk-delete toolbar (hidden until select mode ON)
        self.select_btn = QPushButton("☑  Select")
        self.select_btn.setCursor(Qt.PointingHandCursor)
        self.select_btn.setFixedHeight(40)
        self.select_btn.setFont(QFont("Poppins", 10, QFont.Bold))
        self.select_btn.setStyleSheet(f"""
            QPushButton {{
                background:{RED}; color:white;
                border:1.5px solid white; border-radius:10px;
                padding:0 16px;
            }}
            QPushButton:hover {{ background:{RED_DARK}; }}
        """)
        self.select_btn.clicked.connect(self._toggle_select_mode)

        self.cancel_select_btn = QPushButton("Cancel")
        self.cancel_select_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_select_btn.setFixedHeight(40)
        self.cancel_select_btn.setFont(QFont("Poppins", 10, QFont.Bold))
        self.cancel_select_btn.setStyleSheet(f"""
            QPushButton {{
                background:white; color:{MUTED};
                border:1.5px solid #ccc; border-radius:10px;
                padding:0 16px;
            }}
            QPushButton:hover {{ background:#f5f5f5; }}
        """)
        self.cancel_select_btn.clicked.connect(self._exit_select_mode)
        self.cancel_select_btn.hide()

        self.delete_selected_btn = QPushButton("🗑  Delete Selected")
        self.delete_selected_btn.setCursor(Qt.PointingHandCursor)
        self.delete_selected_btn.setFixedHeight(40)
        self.delete_selected_btn.setFont(QFont("Poppins", 10, QFont.Bold))
        self.delete_selected_btn.setStyleSheet(f"""
            QPushButton {{
                background:{RED}; color:white;
                border:none; border-radius:10px;
                padding:0 16px;
            }}
            QPushButton:hover {{ background:{RED_DARK}; }}
        """)
        self.delete_selected_btn.clicked.connect(self._bulk_delete)
        self.delete_selected_btn.hide()

        self.selected_count_lbl = QLabel("")
        self.selected_count_lbl.setFont(QFont("Poppins", 10))
        self.selected_count_lbl.setStyleSheet(
            f"color:{MUTED}; background:transparent;")
        self.selected_count_lbl.hide()

        # Added Archives Button
        self.archives_btn = QPushButton("📂  Archives")
        self.archives_btn.setCursor(Qt.PointingHandCursor)
        self.archives_btn.setFixedHeight(40)
        self.archives_btn.setFont(QFont("Poppins", 10, QFont.Bold))
        self.archives_btn.setStyleSheet(
            f"QPushButton {{ background:{RED}; color:white; border:1.5px solid white; border-radius:10px; padding:0 16px; }} QPushButton:hover {{ background:{RED_DARK}; }}")
        self.archives_btn.clicked.connect(self._open_archives)

        title_row.addWidget(self.title_label)
        title_row.addStretch()
        title_row.addWidget(self.selected_count_lbl)
        title_row.addSpacing(8)
        title_row.addWidget(self.cancel_select_btn)
        title_row.addSpacing(8)
        title_row.addWidget(self.delete_selected_btn)
        title_row.addSpacing(8)
        title_row.addWidget(self.archives_btn)
        title_row.addSpacing(8)
        title_row.addWidget(self.select_btn)

        # Filter bar
        self.filter_card = QFrame()
        self.filter_card.setStyleSheet(f"""
            QFrame {{ background:{CARD}; border:1px solid {RED_BORDER};
                      border-radius:18px; }}
        """)
        filter_layout = QVBoxLayout(self.filter_card)
        filter_layout.setContentsMargins(18, 16, 18, 16)
        filter_layout.setSpacing(0)

        top_filter_row = QHBoxLayout()
        top_filter_row.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by ID or student name...")
        self.search_input.setFixedHeight(48)
        self.search_input.setFont(QFont("Poppins", 11))
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background:white; border:1.5px solid {RED_BORDER};
                border-radius:12px; padding:0 16px; color:{TEXT};
            }}
            QLineEdit:focus {{ border:1.5px solid {RED}; }}
        """)
        self.search_input.textChanged.connect(self.apply_filters)

        self.gender_filter = self._combo(
            ["All Gender", "Male", "Female", "Other"])
        self.age_filter = self._combo(
            ["All Age"] + [str(a) for a in range(17, 31)])
        self.department_filter = self._combo(
            ["All Department"] + DEPARTMENTS)
        self.status_filter = self._combo(
            ["All Status"] + STATUS_OPTIONS)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setCursor(Qt.PointingHandCursor)
        self.reset_btn.setFixedHeight(48)
        self.reset_btn.setFixedWidth(96)
        self.reset_btn.setFont(QFont("Poppins", 11, QFont.Bold))
        self.reset_btn.setStyleSheet(f"""
            QPushButton {{
                background:{RED}; color:white;
                border:none; border-radius:12px;
            }}
            QPushButton:hover {{ background:{RED_DARK}; }}
        """)
        self.reset_btn.clicked.connect(self.reset_filters)

        top_filter_row.addWidget(self.search_input, 4)
        top_filter_row.addWidget(self.gender_filter, 1)
        top_filter_row.addWidget(self.age_filter, 1)
        top_filter_row.addWidget(self.department_filter, 2)
        top_filter_row.addWidget(self.status_filter, 2)
        top_filter_row.addWidget(self.reset_btn)
        filter_layout.addLayout(top_filter_row)

        # Table card
        self.table_card = QFrame()
        self.table_card.setStyleSheet(f"""
            QFrame {{ background:{CARD}; border:1px solid {RED_BORDER};
                      border-radius:18px; }}
        """)
        table_layout = QVBoxLayout(self.table_card)
        table_layout.setContentsMargins(14, 14, 14, 14)

        self.table = QTableWidget()
        self.table.setColumnCount(self.COL_COUNT)
        self.table.setHorizontalHeaderLabels([
            "", "ID", "STUDENT NAME", "GENDER", "AGE",
            "DEPARTMENT", "STATUS", ""
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setMouseTracking(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background:white; border:none; border-radius:12px;
                color:{TEXT}; font-family:'Poppins'; font-size:13px;
            }}
            QHeaderView::section {{
                background:{HEADER_BG}; color:{RED}; border:none;
                border-bottom:1px solid #f0cad3; padding:16px 18px;
                font-family:'Poppins'; font-size:12px; font-weight:700;
            }}
            QTableWidget::item {{
                border-bottom:1px solid #f4dde3; padding:14px 18px;
            }}
            QTableWidget::item:hover {{ background:{ROW_HOVER}; }}
        """)

        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        modes = [
            QHeaderView.Fixed,  # checkbox
            QHeaderView.Fixed,  # ID
            QHeaderView.Stretch,  # name
            QHeaderView.Fixed,  # gender
            QHeaderView.Fixed,  # age
            QHeaderView.Fixed,  # dept
            QHeaderView.Fixed,  # status
            QHeaderView.Fixed,  # action
        ]
        for i, mode in enumerate(modes):
            header.setSectionResizeMode(i, mode)

        self.table.setColumnWidth(self.COL_CHECK, 0)  # hidden by default
        self.table.setColumnWidth(self.COL_ID, 170)
        self.table.setColumnWidth(self.COL_GENDER, 130)
        self.table.setColumnWidth(self.COL_AGE, 90)
        self.table.setColumnWidth(self.COL_DEPT, 150)
        self.table.setColumnWidth(self.COL_STATUS, 150)
        self.table.setColumnWidth(self.COL_ACTION, 60)

        # Header checkbox for select-all
        self.header_checkbox = QCheckBox()
        self.header_checkbox.setStyleSheet(self._checkbox_style())
        self.header_checkbox.stateChanged.connect(self._select_all_toggled)

        # FIX: Keep it hidden from the standard header area (logical column width 0)
        self.table.horizontalHeader().setSectionResizeMode(
            self.COL_CHECK, QHeaderView.Fixed)

        table_layout.addWidget(self.table)

        main_layout.addLayout(title_row)
        main_layout.addWidget(self.filter_card)
        main_layout.addWidget(self.table_card)

    def _checkbox_style(self):
        return f"""
            QCheckBox {{ background:transparent; }}
            QCheckBox::indicator {{
                width:18px; height:18px;
                border:2px solid {RED_BORDER};
                border-radius:4px; background:white;
            }}
            QCheckBox::indicator:checked {{
                background:{RED}; border:2px solid {RED};
                image: none;
            }}
            QCheckBox::indicator:hover {{
                border:2px solid {RED};
            }}
        """

    def _combo(self, items):
        combo = QComboBox()
        combo.addItems(items)
        combo.setFixedHeight(48)
        combo.setFont(QFont("Poppins", 11))
        combo.setCursor(Qt.PointingHandCursor)
        combo.setStyleSheet(f"""
            QComboBox {{
                background:white; border:1.5px solid {RED_BORDER};
                border-radius:12px; padding:0 14px; color:{TEXT};
            }}
            QComboBox:hover {{ border:1.5px solid {RED}; }}
            QComboBox::drop-down {{ border:none; width:28px; }}
            QComboBox QAbstractItemView {{
                background:white; border:1px solid {RED_BORDER};
                selection-background-color:#fdf0f3;
                selection-color:{RED}; color:{TEXT};
                padding:6px; font-size:11px;
            }}
        """)
        combo.currentIndexChanged.connect(self.apply_filters)
        return combo

    # ── Archives ───────────────────────────────────────────────────
    def _open_archives(self):
        dlg = ArchivesWindow(self)
        dlg.restored.connect(self.refresh_table)
        dlg.exec_()

    # ── Select mode ───────────────────────────────────────────────────────────
    def _toggle_select_mode(self):
        self._select_mode = True
        self.select_btn.hide()
        self.archives_btn.hide()
        self.cancel_select_btn.show()
        self.delete_selected_btn.show()
        self.selected_count_lbl.show()
        self.table.setColumnWidth(self.COL_CHECK, 48)
        self._update_selected_count()
        self.load_table()

    def _exit_select_mode(self):
        self._select_mode = False
        self.select_btn.show()
        self.archives_btn.show()
        self.cancel_select_btn.hide()
        self.delete_selected_btn.hide()
        self.selected_count_lbl.hide()
        self.header_checkbox.setCheckState(Qt.Unchecked)
        self.table.setColumnWidth(self.COL_CHECK, 0)
        self.load_table()

    def _select_all_toggled(self, state):
        if not self._select_mode:
            return
        check = Qt.Checked if state == Qt.Checked else Qt.Unchecked
        for row in range(self.table.rowCount()):
            cb_widget = self.table.cellWidget(row, self.COL_CHECK)
            if cb_widget:
                cb = cb_widget.findChild(QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setCheckState(check)
                    cb.blockSignals(False)
        self._update_selected_count()

    def _on_row_checkbox(self):
        self._update_selected_count()

    def _update_selected_count(self):
        count = self._get_checked_rows().__len__()
        self.selected_count_lbl.setText(
            f"{count} student{'s' if count != 1 else ''} selected")

    def _get_checked_rows(self) -> list:
        """Return list of student dicts for all checked rows."""
        checked = []
        for row in range(self.table.rowCount()):
            cb_widget = self.table.cellWidget(row, self.COL_CHECK)
            if cb_widget:
                cb = cb_widget.findChild(QCheckBox)
                if cb and cb.isChecked():
                    checked.append(self.filtered_students[row])
        return checked

    def _bulk_delete(self):
        students = self._get_checked_rows()
        if not students:
            QMessageBox.information(self, "No Selection",
                                    "Please select at least one student to delete.")
            return
        names = "\n".join(
            f"  • {s['name']}" for s in students[:10])
        if len(students) > 10:
            names += f"\n  ... and {len(students) - 10} more"

        reply = QMessageBox.question(
            self, "Confirm Bulk Delete",
            f"You are about to delete {len(students)} student(s):\n\n"
            f"{names}\n\n"
            f"All records will be backed up to deleted_students.db.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                bulk_delete_and_backup(students)
                self._exit_select_mode()
                self.refresh_table()
                QMessageBox.information(self, "Done",
                                        f"{len(students)} student(s) deleted and backed up.")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Database Error",
                                     f"Failed to delete students:\n{e}")

    # ── Data ──────────────────────────────────────────────────────────────────
    def refresh_table(self):
        self.all_students = fetch_all_students()
        self.apply_filters()

    def reset_filters(self):
        self.search_input.clear()
        for combo in (self.gender_filter, self.age_filter,
                      self.department_filter, self.status_filter):
            combo.setCurrentIndex(0)
        self.apply_filters()

    def apply_filters(self):
        kw = self.search_input.text().strip().lower()
        gend = self.gender_filter.currentText()
        age = self.age_filter.currentText()
        dept = self.department_filter.currentText()
        stat = self.status_filter.currentText()

        results = []
        for s in self.all_students:
            if kw and kw not in s["id"].lower() \
                    and kw not in s["name"].lower():
                continue
            if gend != "All Gender" and s["gender"] != gend: continue
            if age != "All Age" and str(s["age"]) != age:  continue
            if dept != "All Department" and s["department"] != dept: continue
            if stat != "All Status" and s["status"] != stat: continue
            results.append(s)

        self.filtered_students = results
        self.load_table()

    # ── Table render ──────────────────────────────────────────────────────────
    def _item(self, value, align=Qt.AlignLeft | Qt.AlignVCenter):
        it = QTableWidgetItem(str(value))
        it.setForeground(QColor(TEXT))
        it.setTextAlignment(align)
        it.setFont(QFont("Poppins", 11))
        return it

    def _make_checkbox_cell(self):
        """FIX: Centred checkbox widget for a table cell with zero margins to prevent clipping."""
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(wrap)
        # Fix: Removing margins ensures the checkbox isn't pushed out of bounds
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignCenter)
        cb = QCheckBox()
        cb.setFixedSize(20, 20)  # Constrain size to ensure it fits the column
        cb.setStyleSheet(self._checkbox_style())
        cb.stateChanged.connect(self._on_row_checkbox)
        lay.addWidget(cb)
        return wrap

    def load_table(self):
        self.table.clearSpans()
        self.table.clearContents()
        self.table.setRowCount(0)

        # Show/hide header checkbox column width
        self.table.setColumnWidth(
            self.COL_CHECK, 48 if self._select_mode else 0)

        if not self.filtered_students:
            self.table.setRowCount(1)
            self.table.setSpan(0, 0, 1, self.COL_COUNT)
            empty = QTableWidgetItem("No students found.")
            empty.setForeground(QColor(MUTED))
            empty.setTextAlignment(Qt.AlignCenter)
            empty.setFont(QFont("Poppins", 12))
            self.table.setItem(0, 0, empty)
            self.table.setRowHeight(0, 80)
            return

        self.table.setRowCount(len(self.filtered_students))
        for row, s in enumerate(self.filtered_students):
            self.table.setRowHeight(row, 64)

            # Checkbox (visible only in select mode)
            if self._select_mode:
                self.table.setCellWidget(
                    row, self.COL_CHECK, self._make_checkbox_cell())

            self.table.setItem(row, self.COL_ID, self._item(s["id"]))
            self.table.setItem(row, self.COL_NAME, self._item(s["name"]))
            self.table.setItem(row, self.COL_GENDER, self._item(s["gender"]))
            self.table.setItem(row, self.COL_AGE, self._item(s["age"]))
            self.table.setItem(row, self.COL_DEPT, self._item(s["department"]))
            self.table.setItem(row, self.COL_STATUS, self._item(s["status"]))
            self.table.setCellWidget(
                row, self.COL_ACTION,
                ActionButton(s, self.refresh_table))


# ── Standalone run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ViewAllStudentsWindow()
    window.show()
    sys.exit(app.exec_())