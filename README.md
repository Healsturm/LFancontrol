# LFancontrol
List the fan speeds, try to change the speed of the selected fan using the slider.
General Architecture

Language: Python 3

GUI toolkit: Qt (PySide6 or PyQt6; we will choose one of them)

Backend: Directly reading sensor/fan information from hwmon* folders under /sys/class/hwmon.

Permissions: Writing to PWM files generally requires root access; initially:

Read side with a normal user,

Write side with an error message if no permissions are granted, and preparation for future polkit/sudo integration.


<img width="521" height="358" alt="Ekran Görüntüsü - 2026-02-17 19-41-40" src="https://github.com/user-attachments/assets/1ebcdc67-8b71-4aa3-9af0-71679db9a978" />
GUI Design

Main window components (e.g., main_window.py):

Left side: Fan list (QListWidget or QComboBox)

Each line: Display in the format "Device name - Fan X (RPM: YYY)".

Middle/right side: Detail panel for the selected fan:

Label: fan name

Label: current RPM value (updated periodically)

Slider: PWM value (0–255 or detected range)

Label: current PWM percentage (e.g., 50%)

Buttons (optional in the initial version): Refresh, Return to Auto mode (if pwm_enable support is available)

Update mechanism:

QTimer reads the RPM of the selected fan at specific intervals (e.g., 1 second) and updates the label.

When the slider moves, set_pwm is called to the backend; an error message is displayed if the write fails.
Error and Permission Management (GUI Side)

Permission Errors:

If a PWM write attempt returns a PermissionError, display a warning with a QMessageBox:

A message such as, "This fan requires root privileges to be controlled manually. Consider running the application with sudo or adding the appropriate udev/polkit rule."

If no hardware support is found:

Display an informative message in the main window if no fans are found (e.g., "No suitable fan sensor found").

File/Directory Structure Suggestion

backend.py: HwmonFan, HwmonScanner, low-level read/write functions.

ui_main.py or main_window.py: Qt main window class.

app.py: Qt QApplication starting point.

requirements.txt: PySide6 or PyQt6 list.

README.md: Usage instructions (e.g., "read-only without root", "root privileges for PWM") and known constraints.
