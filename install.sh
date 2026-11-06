#!/usr/bin/env bash
# Установщик прототипа «Проверка условий договоров поставки».
# Создаёт виртуальное окружение, ставит зависимости и запускает сервис.
# Использование:  ./install.sh [--port 8000]
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
for arg in "$@"; do
  case "$arg" in
    --port=*) PORT="${arg#*=}" ;;
    --port) shift; PORT="${1:-8000}" ;;
  esac
done

PY=python3
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "Ошибка: python3 не найден. Установите Python 3.10+." >&2
  exit 1
fi

# Проверка версии Python (>= 3.10)
"$PY" - <<'PY'
import sys
if sys.version_info < (3, 10):
    sys.exit("Требуется Python 3.10 или новее (установлен %s)" % sys.version.split()[0])
PY

VENV=".venv"
if [ ! -d "$VENV" ]; then
  echo "==> Создаю виртуальное окружение $VENV ..."
  "$PY" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "==> Устанавливаю зависимости ..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

echo
echo "Готово. Запускаю сервис на http://127.0.0.1:${PORT}"
echo "Для остановки нажмите Ctrl+C."
echo
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
