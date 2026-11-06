.PHONY: run test docker-build docker-up docker-down install clean

# Локальный запуск (venv)
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Тесты
test:
	pytest -q

# Docker
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Установка в venv
install:
	./install.sh

clean:
	rm -rf .venv __pycache__ .pytest_cache
