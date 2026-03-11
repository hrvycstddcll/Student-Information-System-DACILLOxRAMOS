# Student Information System (SIS)

A professional desktop-based management system developed using Python and PyQt5. This system provides a secure environment for managing student data with an integrated archival protocol for data preservation.

## 👥 Development Team
* **Harvey Dacillo** – Backend Developer & Database Architect
* **Joenalyn Ramos** – UI/UX Designer & Frontend Developer

## 🔐 Administrative Access
To access the management dashboard, use the following credentials:
* **Username:** `admin`
* **Password:** `Admin@123`

## 📋 Key Features
* **Student Lifecycle Management**: Full CRUD (Create, Read, Update, Delete) capabilities for student records.
* **Archival System**: Automatically moves deleted records to `deleted_students.db` with a timestamp to prevent permanent data loss.
* **Advanced Search**: Real-time filtering by Name, ID, Department, and Status.
* **Bulk Processing**: Toggleable "Select Mode" for efficiently archiving multiple records at once.

## 📂 Project Structure
The system is organized into a modular directory for better maintainability:
* **`main.py`**: The entry point for the application.
* **`dashboard.py`**: The primary navigation hub after login.
* **`/assets/`**: Contains UI components, custom fonts, and images.
    * `ui/add_student.py`: Interface for registering new students.
    * `ui/view_all_students.py`: Management interface for viewing and archiving records.
* **`/database/`**: Stores persistent SQLite data.
    * `sis_users.db`: Primary database for active student records.
    * `deleted_students.db`: Secure backup for archived data.



## 🚀 Installation & Setup

1. **Dependencies**:
   To ensure PyQt5 is installed for your specific Python version, run:
   ```bash
   python -m pip install PyQt5
