#!/usr/bin/env python3
"""PWM değerini yazmak için pkexec ile çalıştırılacak helper script."""
import sys

if len(sys.argv) != 3:
    print("Kullanım: write_pwm.py <pwm_dosya_yolu> <değer>", file=sys.stderr)
    sys.exit(1)

pwm_path = sys.argv[1]
value = sys.argv[2]

try:
    with open(pwm_path, "w", encoding="utf-8") as f:
        f.write(f"{value}\n")
    print("OK")
except Exception as e:
    print(f"HATA: {e}", file=sys.stderr)
    sys.exit(1)
