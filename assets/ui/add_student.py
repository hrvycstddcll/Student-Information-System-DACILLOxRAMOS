import sys
import os
import sqlite3

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QFrame,
    QLineEdit,
    QComboBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
)


RED       = "#b90d33"
RED_DARK  = "#990a2a"
RED_BORDER = "#e7bcc5"
BG        = "#f7f7f9"
CARD      = "#ffffff"
TEXT      = "#3f3f46"
MUTED     = "#7a7a7a"

DEPARTMENTS    = ["CABEIHM", "CAS", "CCJE", "CHS", "CICS", "CTE"]
STATUS_OPTIONS = ["Regular", "Irregular", "Transferee"]

# ── Database path (relative to project root) ──────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "..", "database", "sis_users.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_students_table():
    """Create the students table if it doesn't exist yet."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id               TEXT PRIMARY KEY,
                first_name       TEXT NOT NULL,
                middle_name      TEXT,
                last_name        TEXT NOT NULL,
                suffix           TEXT,
                age              INTEGER NOT NULL,
                gender           TEXT NOT NULL,
                department       TEXT NOT NULL,
                status           TEXT NOT NULL,
                year_level       TEXT,
                contact          TEXT,
                email            TEXT,
                guardian_name    TEXT,
                guardian_contact TEXT,
                address          TEXT
            )
        """)
        conn.commit()


def student_id_exists(student_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM students WHERE id = ?", (student_id,)
        ).fetchone()
    return row is not None


def insert_student(data: dict):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO students (
                id, first_name, middle_name, last_name, suffix,
                age, gender, department, status, year_level,
                contact, email, guardian_name, guardian_contact, address
            ) VALUES (
                :id, :first_name, :middle_name, :last_name, :suffix,
                :age, :gender, :department, :status, :year_level,
                :contact, :email, :guardian_name, :guardian_contact, :address
            )
        """, data)
        conn.commit()


def update_student(data: dict):
    with get_connection() as conn:
        conn.execute("""
            UPDATE students SET
                first_name       = :first_name,
                middle_name      = :middle_name,
                last_name        = :last_name,
                suffix           = :suffix,
                age              = :age,
                gender           = :gender,
                department       = :department,
                status           = :status,
                year_level       = :year_level,
                contact          = :contact,
                email            = :email,
                guardian_name    = :guardian_name,
                guardian_contact = :guardian_contact,
                address          = :address
            WHERE id = :id
        """, data)
        conn.commit()


# ── Window ────────────────────────────────────────────────────────────────────
class RegisterStudentWindow(QWidget):
    def __init__(self, student_data=None):
        super().__init__()
        self.student_data   = student_data
        self.is_update_mode = student_data is not None

        self.setWindowTitle(
            "Update Student" if self.is_update_mode else "Register a Student")
        self.setMinimumSize(1120, 760)
        self.setStyleSheet(f"background:{BG};")

        ensure_students_table()
        self.init_ui()

        if self.is_update_mode:
            self.load_student_data()

    # ── UI build ──────────────────────────────────────────────────────────────
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        self.title = QLabel(
            "Update Student" if self.is_update_mode else "Register a Student")
        self.title.setFont(QFont("Poppins", 24, QFont.Bold))
        self.title.setStyleSheet(
            f"color:{RED}; background:transparent; border:none;")

        subtitle_text = (
            "Modify the student information below"
            if self.is_update_mode
            else "Fill out the student information form"
        )
        self.subtitle = QLabel(subtitle_text)
        self.subtitle.setFont(QFont("Poppins", 11))
        self.subtitle.setStyleSheet(
            f"color:{MUTED}; background:transparent; border:none;")

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(4)
        title_wrap.addWidget(self.title)
        title_wrap.addWidget(self.subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        scroll.setWidget(container)

        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.setAlignment(Qt.AlignTop)

        form_card = QFrame()
        form_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        form_card.setStyleSheet(f"""
            QFrame {{
                background: {CARD};
                border: 1px solid {RED_BORDER};
                border-radius: 18px;
            }}
        """)

        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(24, 22, 24, 22)
        form_layout.setSpacing(22)

        section_title = QLabel("Student Information")
        section_title.setFont(QFont("Poppins", 16, QFont.Bold))
        section_title.setStyleSheet(
            "color:#b90d33; background:transparent; border:none;")

        form_grid = QGridLayout()
        form_grid.setHorizontalSpacing(18)
        form_grid.setVerticalSpacing(16)

        self.student_id_input  = self.create_input("Enter student ID")
        self.age_input         = self.create_input("Enter age")
        self.gender_input      = self.create_combo(
            ["Select gender", "Male", "Female", "Other"])

        form_grid.addWidget(
            self.create_field("Student ID *", self.student_id_input), 0, 0)
        form_grid.addWidget(
            self.create_field("Age *", self.age_input), 0, 1)
        form_grid.addWidget(
            self.create_field("Gender *", self.gender_input), 0, 2)

        self.first_name_input  = self.create_input("Enter first name")
        self.middle_name_input = self.create_input("Enter middle name")
        self.last_name_input   = self.create_input("Enter last name")

        form_grid.addWidget(
            self.create_field("First Name *", self.first_name_input), 1, 0)
        form_grid.addWidget(
            self.create_field("Middle Name", self.middle_name_input), 1, 1)
        form_grid.addWidget(
            self.create_field("Last Name *", self.last_name_input), 1, 2)

        self.suffix_input     = self.create_input("Jr., Sr., III, etc.")
        self.department_input = self.create_combo(
            ["Select department"] + DEPARTMENTS)
        self.status_input     = self.create_combo(
            ["Select status"] + STATUS_OPTIONS)

        form_grid.addWidget(
            self.create_field("Suffix", self.suffix_input), 2, 0)
        form_grid.addWidget(
            self.create_field("Department *", self.department_input), 2, 1)
        form_grid.addWidget(
            self.create_field("Status *", self.status_input), 2, 2)

        self.year_level_input = self.create_combo([
            "Select year level",
            "1st Year", "2nd Year", "3rd Year", "4th Year"
        ])
        self.contact_input = self.create_input("Enter contact number")
        self.email_input   = self.create_input("Enter email address")

        form_grid.addWidget(
            self.create_field("Year Level", self.year_level_input), 3, 0)
        form_grid.addWidget(
            self.create_field("Contact Number", self.contact_input), 3, 1)
        form_grid.addWidget(
            self.create_field("Email Address", self.email_input), 3, 2)

        self.guardian_name_input    = self.create_input("Enter guardian name")
        self.guardian_contact_input = self.create_input(
            "Enter guardian contact number")
        self.address_input          = self.create_input(
            "Enter complete address")

        form_grid.addWidget(
            self.create_field("Guardian Name", self.guardian_name_input), 4, 0)
        form_grid.addWidget(
            self.create_field("Guardian Contact",
                              self.guardian_contact_input), 4, 1)
        form_grid.addWidget(
            self.create_field("Address", self.address_input), 4, 2)

        button_row = QHBoxLayout()
        button_row.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setFixedSize(120, 46)
        self.clear_btn.setFont(QFont("Poppins", 11, QFont.Bold))
        self.clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: white; color: {RED};
                border: 1.5px solid {RED}; border-radius: 12px;
            }}
            QPushButton:hover {{ background: #fff5f7; }}
        """)
        self.clear_btn.clicked.connect(self.clear_form)

        btn_text = "Save Changes" if self.is_update_mode else "Register Student"
        self.save_btn = QPushButton(btn_text)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedSize(180, 46)
        self.save_btn.setFont(QFont("Poppins", 11, QFont.Bold))
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {RED}; color: white;
                border: none; border-radius: 12px;
            }}
            QPushButton:hover {{ background: {RED_DARK}; }}
        """)
        self.save_btn.clicked.connect(self.submit_form)

        button_row.addWidget(self.clear_btn)
        button_row.addSpacing(10)
        button_row.addWidget(self.save_btn)

        form_layout.addWidget(section_title)
        form_layout.addLayout(form_grid)
        form_layout.addSpacing(8)
        form_layout.addLayout(button_row)

        container_layout.addWidget(form_card, 0, Qt.AlignTop)
        container_layout.addSpacing(40)

        main_layout.addLayout(title_wrap)
        main_layout.addWidget(scroll)

    # ── Widget helpers ────────────────────────────────────────────────────────
    def create_input(self, placeholder):
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(46)
        field.setFont(QFont("Poppins", 10))
        field.setStyleSheet(f"""
            QLineEdit {{
                background: white;
                border: 1.5px solid {RED_BORDER};
                border-radius: 12px;
                padding: 0 14px;
                color: {TEXT};
            }}
            QLineEdit:focus {{ border: 1.5px solid {RED}; }}
        """)
        return field

    def create_combo(self, items):
        combo = QComboBox()
        combo.addItems(items)
        combo.setFixedHeight(46)
        combo.setFont(QFont("Poppins", 10))
        combo.setCursor(Qt.PointingHandCursor)
        combo.setStyleSheet(f"""
            QComboBox {{
                background: white;
                border: 1.5px solid {RED_BORDER};
                border-radius: 12px;
                padding: 0 14px;
                color: {TEXT};
            }}
            QComboBox:hover {{ border: 1.5px solid {RED}; }}
            QComboBox::drop-down {{ border: none; width: 28px; }}
            QComboBox QAbstractItemView {{
                background: white;
                border: 1px solid {RED_BORDER};
                selection-background-color: #fdf0f3;
                selection-color: {RED};
                color: {TEXT};
            }}
        """)
        return combo

    def create_field(self, label_text, widget):
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        label = QLabel(label_text)
        label.setFont(QFont("Poppins", 10, QFont.Bold))
        label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT}; background: transparent;
                border: none; padding: 0px; margin: 0px;
            }}
        """)
        layout.addWidget(label)
        layout.addWidget(widget)
        return wrapper

    # ── Data helpers ──────────────────────────────────────────────────────────
    def set_combo_value(self, combo, value):
        index = combo.findText(str(value), Qt.MatchFixedString)
        if index >= 0:
            combo.setCurrentIndex(index)

    def split_name(self, full_name):
        parts = full_name.strip().split()
        if len(parts) == 0:  return "", "", ""
        if len(parts) == 1:  return parts[0], "", ""
        if len(parts) == 2:  return parts[0], "", parts[1]
        return parts[0], " ".join(parts[1:-1]), parts[-1]

    def load_student_data(self):
        data = self.student_data
        self.student_id_input.setText(str(data.get("id", "")))
        self.age_input.setText(str(data.get("age", "")))

        first_name, middle_name, last_name = self.split_name(
            data.get("name", ""))
        self.first_name_input.setText(first_name)
        self.middle_name_input.setText(middle_name)
        self.last_name_input.setText(last_name)

        self.suffix_input.setText(str(data.get("suffix", "")))
        self.contact_input.setText(str(data.get("contact", "")))
        self.email_input.setText(str(data.get("email", "")))
        self.guardian_name_input.setText(str(data.get("guardian_name", "")))
        self.guardian_contact_input.setText(
            str(data.get("guardian_contact", "")))
        self.address_input.setText(str(data.get("address", "")))

        self.set_combo_value(self.gender_input,     data.get("gender", ""))
        self.set_combo_value(self.department_input, data.get("department", ""))
        self.set_combo_value(self.status_input,     data.get("status", ""))
        self.set_combo_value(self.year_level_input, data.get("year_level", ""))

    def clear_form(self):
        for field in (self.student_id_input, self.age_input,
                      self.first_name_input, self.middle_name_input,
                      self.last_name_input,  self.suffix_input,
                      self.contact_input,    self.email_input,
                      self.guardian_name_input, self.guardian_contact_input,
                      self.address_input):
            field.clear()
        for combo in (self.gender_input, self.department_input,
                      self.status_input, self.year_level_input):
            combo.setCurrentIndex(0)

    # ── Validation & save ─────────────────────────────────────────────────────
    def _collect(self) -> dict | None:
        """Validate inputs and return a data dict, or None if invalid."""
        student_id = self.student_id_input.text().strip()
        first_name = self.first_name_input.text().strip()
        last_name  = self.last_name_input.text().strip()
        age        = self.age_input.text().strip()
        gender     = self.gender_input.currentText()
        department = self.department_input.currentText()
        status     = self.status_input.currentText()

        if not student_id or not first_name or not last_name or not age:
            QMessageBox.warning(self, "Incomplete Form",
                "Please fill in the required fields: "
                "Student ID, First Name, Last Name, and Age.")
            return None
        if gender == "Select gender":
            QMessageBox.warning(self, "Incomplete Form",
                "Please select a gender.")
            return None
        if department == "Select department":
            QMessageBox.warning(self, "Incomplete Form",
                "Please select a department.")
            return None
        if status == "Select status":
            QMessageBox.warning(self, "Incomplete Form",
                "Please select a student status.")
            return None
        if not age.isdigit():
            QMessageBox.warning(self, "Invalid Age",
                "Age must be a number.")
            return None

        year_level = self.year_level_input.currentText()
        if year_level == "Select year level":
            year_level = ""

        return {
            "id":               student_id,
            "first_name":       first_name,
            "middle_name":      self.middle_name_input.text().strip(),
            "last_name":        last_name,
            "suffix":           self.suffix_input.text().strip(),
            "age":              int(age),
            "gender":           gender,
            "department":       department,
            "status":           status,
            "year_level":       year_level,
            "contact":          self.contact_input.text().strip(),
            "email":            self.email_input.text().strip(),
            "guardian_name":    self.guardian_name_input.text().strip(),
            "guardian_contact": self.guardian_contact_input.text().strip(),
            "address":          self.address_input.text().strip(),
        }

    def submit_form(self):
        data = self._collect()
        if data is None:
            return

        try:
            if self.is_update_mode:
                update_student(data)
                QMessageBox.information(self, "Student Updated",
                    f"Student record updated successfully!\n\n"
                    f"ID: {data['id']}\n"
                    f"Name: {data['first_name']} {data['last_name']}\n"
                    f"Department: {data['department']}\n"
                    f"Status: {data['status']}")
            else:
                # Check for duplicate ID before inserting
                if student_id_exists(data["id"]):
                    QMessageBox.warning(self, "Duplicate ID",
                        f"Student ID '{data['id']}' already exists.\n"
                        "Please use a different ID.")
                    return

                insert_student(data)
                QMessageBox.information(self, "Student Registered",
                    f"Student registered successfully!\n\n"
                    f"ID: {data['id']}\n"
                    f"Name: {data['first_name']} {data['last_name']}\n"
                    f"Department: {data['department']}\n"
                    f"Status: {data['status']}")
                self.clear_form()

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error",
                f"Failed to save student record:\n{e}")


# ── Standalone run ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RegisterStudentWindow()
    window.show()
    sys.exit(app.exec_())