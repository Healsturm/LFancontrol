import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Linux Fan Control")
    app.setApplicationDisplayName("Linux Fan Control")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

