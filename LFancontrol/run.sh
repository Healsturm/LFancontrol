#!/usr/bin/env bash

# Bu betiği çalıştırdığınız klasörden uygulamayı tek tıkla başlatmak için:
#   chmod +x run.sh
# ardından dosya yöneticinizden çift tıklayabilirsiniz.

cd "$(dirname "$0")" || exit 1
exec python3 app.py "$@"

