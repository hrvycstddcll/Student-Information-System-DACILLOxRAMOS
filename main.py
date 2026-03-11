import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5 import QtGui

from assets.ui.login import LoginWindow


class ApplicationManager(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.login_window     = None
        self.dashboard_window = None

    # ── Entry point ───────────────────────────────────────────────────────────
    def start(self):
        self.login_window = LoginWindow()
        self.login_window.login_successful.connect(self._on_login)
        self.login_window.showMaximized()

    # ── Login → Dashboard ─────────────────────────────────────────────────────
    def _on_login(self, user: dict):
        try:
            from dashboard import DashboardWindow
        except ImportError as exc:
            QMessageBox.critical(
                None, "Missing module",
                f"Could not load dashboard.py:\n{exc}"
            )
            return

        self.dashboard_window = DashboardWindow(user=user)
        self._connect_dashboard(self.dashboard_window)
        self.login_window.close()
        self.login_window = None
        self.dashboard_window.showMaximized()

    def _connect_dashboard(self, dw):
        """Wire every signal the dashboard can emit."""
        dw.logout_requested.connect(self._on_logout)

        if hasattr(dw, "open_add_student"):
            dw.open_add_student.connect(self._open_add_student)

        if hasattr(dw, "open_view_students"):
            dw.open_view_students.connect(self._open_view_students)

        if hasattr(dw, "open_reports"):
            dw.open_reports.connect(
                lambda: dw._show_toast("Reports — Coming Soon"))

        if hasattr(dw, "open_settings"):
            dw.open_settings.connect(
                lambda: dw._show_toast("Settings — Coming Soon"))

        if hasattr(dw, "profile_btn"):
            dw.profile_btn.clicked.connect(
                lambda: dw._show_toast("Profile — Coming Soon"))

    # ── Dashboard → sub-windows ───────────────────────────────────────────────
    def _open_add_student(self):
        from assets.ui.add_student import RegisterStudentWindow
        self._add_student_win = RegisterStudentWindow()
        self._add_student_win.show()


    def _open_view_students(self):
        try:
            from assets.ui.view_all_students import ViewAllStudentsWindow
        except ImportError as exc:
            QMessageBox.warning(
                None, "Missing module",
                f"Could not load view_all_students.py:\n{exc}"
            )
            return
        self._view_students_win = ViewAllStudentsWindow()
        self._view_students_win.show()

    # ── Logout → back to Login ────────────────────────────────────────────────
    def _on_logout(self):
        if self.dashboard_window:
            self.dashboard_window.close()
            self.dashboard_window = None
        self.start()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    manager = ApplicationManager(sys.argv)
    manager.setWindowIcon(QtGui.QIcon("logo.png"))
    manager.start()
    sys.exit(manager.exec_())