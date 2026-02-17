from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtWidgets

from backend import HwmonFan, HwmonScanner


class MainWindow(QtWidgets.QMainWindow):
    """Fan listesini ve seçili fanın kontrolünü gösteren ana pencere."""

    RPM_UPDATE_INTERVAL_MS = 1000

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        # Görev çubuğu ve başlıkta görünecek isim
        self.setWindowTitle("Linux Fan Control")
        self.resize(520, 260)

        self._scanner = HwmonScanner()
        self._fans: List[HwmonFan] = self._scanner.scan()
        self._current_fan: Optional[HwmonFan] = None
        self.level_buttons: List[QtWidgets.QPushButton] = []

        self._build_ui()
        self._populate_fan_list()
        self._setup_timer()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)

        # Sol: fan listesi
        self.fan_list = QtWidgets.QListWidget()
        self.fan_list.currentRowChanged.connect(self._on_fan_selected)

        # Sağ: detay paneli
        detail_widget = QtWidgets.QWidget()
        detail_layout = QtWidgets.QVBoxLayout(detail_widget)

        # Üst bilgi etiketi (tp fancontrol'deki duruma benzer)
        self.fan_label = QtWidgets.QLabel("Seçili fan: -")
        self.rpm_label = QtWidgets.QLabel("RPM: -")

        # Mod seçimi (Otomatik / Manuel) - tp fancontrol benzeri
        mode_group = QtWidgets.QGroupBox("Mod")
        mode_layout = QtWidgets.QVBoxLayout(mode_group)
        self.mode_auto_radio = QtWidgets.QRadioButton("Otomatik (BIOS/Kernel)")
        self.mode_manual_radio = QtWidgets.QRadioButton("Manuel")
        self.mode_auto_radio.setChecked(True)
        self.mode_auto_radio.toggled.connect(self._on_mode_changed)
        self.mode_manual_radio.toggled.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_auto_radio)
        mode_layout.addWidget(self.mode_manual_radio)

        # Manuel moddaki PWM slider'ı (arka planda dursun; asıl kontrol seviyelerle)
        self.pwm_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.pwm_slider.setRange(0, 255)
        self.pwm_slider.setEnabled(False)
        self.pwm_slider.valueChanged.connect(self._on_pwm_slider_changed)
        self.pwm_slider.sliderReleased.connect(self._apply_pwm_from_slider)

        self.pwm_value_label = QtWidgets.QLabel("PWM: -")

        # tp fancontrol benzeri seviye butonları (0–7)
        level_group = QtWidgets.QGroupBox("Fan Seviyesi")
        level_layout = QtWidgets.QGridLayout(level_group)
        for level in range(8):
            btn = QtWidgets.QPushButton(str(level))
            btn.setEnabled(False)
            btn.setCheckable(True)
            btn.clicked.connect(
                lambda checked, lvl=level: self._on_level_clicked(lvl)
            )
            self.level_buttons.append(btn)
            row, col = divmod(level, 4)
            level_layout.addWidget(btn, row, col)

        self.info_label = QtWidgets.QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray;")

        detail_layout.addWidget(self.fan_label)
        detail_layout.addWidget(self.rpm_label)
        detail_layout.addWidget(mode_group)
        detail_layout.addWidget(level_group)
        # Slider arka planda kalsın; istenirse ileride gelişmiş moda açılabilir.
        self.pwm_slider.hide()
        detail_layout.addWidget(self.pwm_slider)
        detail_layout.addWidget(self.pwm_value_label)
        detail_layout.addWidget(self.info_label)
        detail_layout.addStretch(1)

        if not self._fans:
            # Fan bulunamadıysa, yalnızca bilgilendirici bir mesaj göster.
            empty_label = QtWidgets.QLabel(
                "Uygun fan sensörü bulunamadı.\n"
                "/sys/class/hwmon altında fan*_input dosyaları tespit edilemedi."
            )
            empty_label.setWordWrap(True)
            empty_label.setAlignment(QtCore.Qt.AlignCenter)
            main_layout.addWidget(empty_label)
        else:
            main_layout.addWidget(self.fan_list, 1)
            main_layout.addWidget(detail_widget, 2)

    def _populate_fan_list(self) -> None:
        self.fan_list.clear()
        for fan in self._fans:
            item = QtWidgets.QListWidgetItem(fan.label)
            self.fan_list.addItem(item)

        if self._fans:
            self.fan_list.setCurrentRow(0)

    def _setup_timer(self) -> None:
        self._rpm_timer = QtCore.QTimer(self)
        self._rpm_timer.setInterval(self.RPM_UPDATE_INTERVAL_MS)
        self._rpm_timer.timeout.connect(self._update_rpm_label)
        self._rpm_timer.start()

    # --- Event handlers ---

    def _on_fan_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._fans):
            self._current_fan = None
            self.fan_label.setText("Seçili fan: -")
            self.rpm_label.setText("RPM: -")
            self.pwm_slider.setEnabled(False)
            self.pwm_value_label.setText("PWM: -")
            self.info_label.setText("")
            return

        fan = self._fans[row]
        self._current_fan = fan
        self.fan_label.setText(f"Seçili fan: {fan.label}")
        self._sync_pwm_controls()
        self._update_rpm_label()

    def _on_pwm_slider_changed(self, value: int) -> None:
        if self._current_fan is None:
            return
        percent = int((value / max(1, self._current_fan.max_pwm)) * 100)
        self.pwm_value_label.setText(f"PWM: {value} ({percent}%)")

    def _on_mode_changed(self, checked: bool) -> None:
        # Sinyal her iki radio için de gelir; sadece değişiklik olduğunda UI'yi yenile.
        if not checked:
            return
        fan = self._current_fan

        # Seçili fan yoksa sadece UI'yi güncelle.
        if fan is None:
            self._sync_pwm_controls()
            return

        try:
            if self.mode_manual_radio.isChecked():
                # Manuel moda geçmeye çalış (pwm_enable=1).
                fan.set_manual_mode()
            elif self.mode_auto_radio.isChecked():
                # Otomatik moda dönmeye çalış (pwm_enable=2).
                fan.set_auto_mode()
        except PermissionError:
            QtWidgets.QMessageBox.warning(
                self,
                "İzin Gerekli",
                (
                    "Bu fanın çalışma modunu değiştirmek için root yetkisi gerekiyor.\n"
                    "Uygulamayı sudo ile çalıştırmayı veya uygun bir udev/polkit "
                    "kuralı eklemeyi düşünebilirsiniz."
                ),
            )
        except Exception as exc:  # pylint: disable=broad-except
            QtWidgets.QMessageBox.warning(
                self,
                "Hata",
                f"Fan modunu değiştirirken bir hata oluştu:\n{exc}",
            )

        self._sync_pwm_controls()

    def _apply_pwm_from_slider(self) -> None:
        if self._current_fan is None:
            return
        if self._current_fan.pwm_path is None:
            return

        value = self.pwm_slider.value()
        self._set_pwm_value(value)

    def _set_pwm_value(self, value: int) -> None:
        """Ortak PWM yazma mantığı (slider veya seviye butonlarından çağrılır)."""
        if self._current_fan is None or self._current_fan.pwm_path is None:
            return

        try:
            self._current_fan.set_pwm(value)
            # Başarılı oldu - UI'yi güncelle
            self._sync_pwm_controls()
        except PermissionError:
            # İzin yoksa pkexec ile helper script'i çalıştırmayı dene
            self._set_pwm_with_pkexec(value)
        except RuntimeError as exc:
            QtWidgets.QMessageBox.information(self, "Desteklenmiyor", str(exc))
        except Exception as exc:  # pylint: disable=broad-except
            QtWidgets.QMessageBox.critical(
                self,
                "Hata",
                f"PWM değeri ayarlanırken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _set_pwm_with_pkexec(self, value: int) -> None:
        """pkexec ile PWM değerini yazmayı dener."""
        if self._current_fan is None or self._current_fan.pwm_path is None:
            return

        script_dir = Path(__file__).parent.resolve()
        write_pwm_script = script_dir / "write_pwm.py"

        if not write_pwm_script.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Hata",
                "write_pwm.py helper script bulunamadı.",
            )
            return

        # Mutlak yolu kullan (pkexec root olarak çalıştığı için göreli yol çalışmaz)
        write_pwm_script_abs = str(write_pwm_script.resolve())

        try:
            # Önce pwm_enable'i manuel moda (1) çek (sessizce, başarısız olsa da devam et)
            if self._current_fan.pwm_enable_path:
                try:
                    subprocess.run(
                        [
                            "pkexec",
                            sys.executable,
                            write_pwm_script_abs,
                            str(self._current_fan.pwm_enable_path),
                            "1",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=False,
                    )
                    # pwm_enable başarısız olsa bile PWM'i denemeye devam et
                except Exception:  # pylint: disable=broad-except
                    pass  # pwm_enable başarısız olsa da PWM'i denemeye devam et

            # Şimdi PWM değerini yaz
            result = subprocess.run(
                [
                    "pkexec",
                    sys.executable,
                    write_pwm_script_abs,
                    str(self._current_fan.pwm_path),
                    str(value),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            # Debug: stdout ve stderr'i kontrol et
            stdout_msg = result.stdout.strip()
            stderr_msg = result.stderr.strip()

            if result.returncode == 0:
                # Başarılı - UI'yi güncelle
                # stdout "OK" olmalı (write_pwm.py'den)
                if stdout_msg == "OK" or not stderr_msg:
                    self._sync_pwm_controls()
                    self._update_rpm_label()
                else:
                    # Beklenmeyen durum
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Uyarı",
                        f"PWM yazıldı ama beklenmeyen çıktı:\nstdout: {stdout_msg}\nstderr: {stderr_msg}",
                    )
            else:
                # Hata durumu
                error_msg = stderr_msg or stdout_msg or "Bilinmeyen hata"
                QtWidgets.QMessageBox.warning(
                    self,
                    "İzin Hatası",
                    (
                        f"PWM değeri ayarlanamadı:\n"
                        f"Return code: {result.returncode}\n"
                        f"stderr: {error_msg}\n"
                        f"stdout: {stdout_msg}\n\n"
                        "Şifre girişi iptal edildi veya yetki verilmedi."
                    ),
                )
        except subprocess.TimeoutExpired:
            QtWidgets.QMessageBox.warning(
                self,
                "Zaman Aşımı",
                "İşlem çok uzun sürdü, iptal edildi.",
            )
        except FileNotFoundError:
            QtWidgets.QMessageBox.warning(
                self,
                "Hata",
                "pkexec bulunamadı. Lütfen polkit paketinin kurulu olduğundan emin olun.",
            )
        except Exception as exc:  # pylint: disable=broad-except
            QtWidgets.QMessageBox.critical(
                self,
                "Hata",
                f"PWM ayarlanırken beklenmeyen bir hata oluştu:\n{exc}",
            )

    def _on_level_clicked(self, level: int) -> None:
        """tp fancontrol'deki gibi 0–7 seviye butonuna basıldığında çağrılır."""
        if self._current_fan is None or self._current_fan.pwm_path is None:
            return
        if hasattr(self, "mode_auto_radio") and self.mode_auto_radio.isChecked():
            # Otomatik modda manuel seviye uygulama.
            return

        pwm = self._level_to_pwm(level, self._current_fan.max_pwm)
        self._set_pwm_value(pwm)
        # UI güncellemesi _set_pwm_value içinde yapılıyor (pkexec başarılı olduğunda)

    # --- Yardımcılar ---

    def _sync_pwm_controls(self) -> None:
        """Seçili fanın PWM desteğine göre slider'ı yapılandır."""
        fan = self._current_fan
        if fan is None or fan.pwm_path is None:
            self.pwm_slider.setEnabled(False)
            for btn in self.level_buttons:
                btn.setEnabled(False)
                btn.setChecked(False)
            self.pwm_value_label.setText("PWM: desteklenmiyor")
            if fan is not None:
                self.info_label.setText(
                    "Bu fan için PWM kontrol dosyası bulunamadı; yalnızca RPM okunabilir."
                )
            else:
                self.info_label.setText("")
            return

        # Otomatik mod seçiliyse, tp fancontrol'deki 'Smart/Bios' moda benzer şekilde
        # slider'ı devre dışı bırakıyoruz.
        if hasattr(self, "mode_auto_radio") and self.mode_auto_radio.isChecked():
            self.pwm_slider.setEnabled(False)
            for btn in self.level_buttons:
                btn.setEnabled(False)
        else:
            self.pwm_slider.setEnabled(True)
            for btn in self.level_buttons:
                btn.setEnabled(True)

        self.pwm_slider.setRange(fan.min_pwm, fan.max_pwm)

        try:
            current_pwm = fan.read_pwm()
        except PermissionError:
            current_pwm = None

        if current_pwm is not None:
            self.pwm_slider.blockSignals(True)
            self.pwm_slider.setValue(current_pwm)
            self.pwm_slider.blockSignals(False)
            percent = int((current_pwm / max(1, fan.max_pwm)) * 100)
            self.pwm_value_label.setText(f"PWM: {current_pwm} ({percent}%)")
            self.info_label.setText("")

            # Mevcut PWM değerine en yakın seviye butonunu işaretle.
            level = self._pwm_to_level(current_pwm, fan.max_pwm)
            self._update_level_buttons(level)
        else:
            self.pwm_value_label.setText("PWM: N/A")
            self.info_label.setText(
                "PWM değeri okunamadı. Bu, izin eksikliğinden veya donanım "
                "kısıtlamasından kaynaklanıyor olabilir."
            )

    def _update_level_buttons(self, active_level: int) -> None:
        for idx, btn in enumerate(self.level_buttons):
            btn.setChecked(idx == active_level)

    @staticmethod
    def _level_to_pwm(level: int, max_pwm: int) -> int:
        """0–7 seviye değerlerini PWM aralığına ölçekler."""
        level = max(0, min(7, level))
        # Basit lineer ölçekleme: 0 -> 0, 7 -> max_pwm
        return int((level / 7.0) * max_pwm)

    @staticmethod
    def _pwm_to_level(pwm: int, max_pwm: int) -> int:
        """PWM değerinden yaklaşık seviye (0–7) hesaplar."""
        if max_pwm <= 0:
            return 0
        ratio = pwm / max_pwm
        level = int(round(ratio * 7))
        return max(0, min(7, level))

    def _update_rpm_label(self) -> None:
        fan = self._current_fan
        if fan is None:
            self.rpm_label.setText("RPM: -")
            return

        try:
            rpm = fan.read_rpm()
        except PermissionError:
            self.rpm_label.setText("RPM: izin yok")
            return

        if rpm is None:
            self.rpm_label.setText("RPM: N/A")
        else:
            self.rpm_label.setText(f"RPM: {rpm}")

