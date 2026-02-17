from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


HWMON_ROOT = Path("/sys/class/hwmon")


@dataclass
class HwmonFan:
    """Tek bir fan sensörü ve (varsa) PWM kontrolünü temsil eder."""

    id: str
    label: str
    rpm_path: Path
    pwm_path: Optional[Path] = None
    pwm_enable_path: Optional[Path] = None
    min_pwm: int = 0
    max_pwm: int = 255

    def _read_int_file(self, path: Path) -> Optional[int]:
        try:
            with path.open("r", encoding="utf-8") as f:
                value = f.read().strip()
            if not value:
                return None
            return int(value)
        except FileNotFoundError:
            return None
        except PermissionError:
            # Üst katman detaylı mesaj gösterecek.
            raise
        except (OSError, ValueError):
            return None

    def _write_int_file(self, path: Path, value: int) -> None:
        try:
            with path.open("w", encoding="utf-8") as f:
                f.write(f"{value}\n")
        except PermissionError:
            # GUI tarafında özel mesaj gösterilebilmesi için tekrar fırlatıyoruz.
            raise
        except OSError as exc:
            # Diğer yazma hatalarını üst kata ilet.
            raise exc

    def read_rpm(self) -> Optional[int]:
        """RPM değerini oku. Okunamazsa None döndür."""
        return self._read_int_file(self.rpm_path)

    def read_pwm(self) -> Optional[int]:
        """PWM değerini oku. PWM desteği yoksa veya okunamazsa None."""
        if self.pwm_path is None:
            return None
        return self._read_int_file(self.pwm_path)

    def _ensure_manual_mode(self) -> None:
        """Mümkünse pwm_enable dosyasını manuel moda (1) çek."""
        if self.pwm_enable_path is None:
            return
        try:
            current = self._read_int_file(self.pwm_enable_path)
            if current != 1:
                self._write_int_file(self.pwm_enable_path, 1)
        except PermissionError:
            # Yetki yoksa GUI'de yakalanacak.
            raise
        except OSError:
            # Diğer hatalar sessiz geçilebilir; PWM yine de denenir.
            return

    def set_manual_mode(self) -> None:
        """Fanı manuel moda almaya çalışır (pwm_enable=1).

        Donanım pwm_enable dosyası sağlamıyorsa sessizce geri döner.
        """
        if self.pwm_enable_path is None:
            return
        self._ensure_manual_mode()

    def set_auto_mode(self) -> None:
        """Fanı otomatik moda almaya çalışır (pwm_enable=2).

        Birçok sürücüde 2 değeri BIOS/kernel tarafından yönetilen otomatik modu temsil eder.
        Donanım pwm_enable dosyası sağlamıyorsa sessizce geri döner.
        """
        if self.pwm_enable_path is None:
            return
        self._write_int_file(self.pwm_enable_path, 2)

    def set_pwm(self, value: int) -> None:
        """PWM değerini ayarla. İzin yoksa PermissionError fırlatabilir."""
        if self.pwm_path is None:
            raise RuntimeError("Bu fan için PWM kontrolü desteklenmiyor.")

        # Sınırlandırma
        clamped = max(self.min_pwm, min(self.max_pwm, value))

        # Mümkünse manuel moda çek
        self._ensure_manual_mode()

        # Değeri yaz
        self._write_int_file(self.pwm_path, clamped)


class HwmonScanner:
    """`/sys/class/hwmon` altında fanları tarar."""

    def __init__(self, root: Path = HWMON_ROOT) -> None:
        self.root = root

    def scan(self) -> List[HwmonFan]:
        fans: List[HwmonFan] = []

        if not self.root.exists():
            return fans

        for entry in sorted(self.root.iterdir()):
            if not entry.name.startswith("hwmon"):
                continue
            if not entry.is_dir():
                continue

            chip_name = self._read_chip_name(entry) or entry.name
            fans.extend(self._scan_hwmon_dir(entry, chip_name))

        return fans

    def _read_chip_name(self, hwmon_dir: Path) -> Optional[str]:
        name_file = hwmon_dir / "name"
        try:
            with name_file.open("r", encoding="utf-8") as f:
                return f.read().strip() or None
        except (FileNotFoundError, PermissionError, OSError):
            return None

    def _scan_hwmon_dir(self, hwmon_dir: Path, chip_name: str) -> List[HwmonFan]:
        fans: List[HwmonFan] = []

        # fanX_input dosyalarını bul
        for file in sorted(hwmon_dir.iterdir()):
            if not file.name.startswith("fan") or not file.name.endswith("_input"):
                continue

            base = file.name[:-len("_input")]  # "fan1_input" -> "fan1"
            index = base[3:]  # "fan1" -> "1"

            rpm_path = file
            pwm_path = hwmon_dir / f"pwm{index}"
            pwm_enable_path = hwmon_dir / f"pwm{index}_enable"

            pwm_exists = pwm_path.exists()
            pwm_enable_exists = pwm_enable_path.exists()

            label = f"{chip_name} - Fan {index}"
            fan_id = f"{chip_name}_fan{index}"

            fan = HwmonFan(
                id=fan_id,
                label=label,
                rpm_path=rpm_path,
                pwm_path=pwm_path if pwm_exists else None,
                pwm_enable_path=pwm_enable_path if pwm_enable_exists else None,
                min_pwm=0,
                max_pwm=255,
            )
            fans.append(fan)

        return fans


if __name__ == "__main__":
    scanner = HwmonScanner()
    detected = scanner.scan()

    if not detected:
        print("Hiç fan bulunamadı (/sys/class/hwmon altında uygun sensör yok).")
    else:
        for fan in detected:
            try:
                rpm = fan.read_rpm()
            except PermissionError:
                rpm = None
            print(f"{fan.label}: RPM={rpm if rpm is not None else 'N/A'}")

