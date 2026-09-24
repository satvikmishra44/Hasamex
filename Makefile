.PHONY: install ingest run test docker-build docker-ingest docker-up docker-down

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt

ingest:
	python -m backend.seed_data

run:
	uvicorn backend.main:app --reload --port 8000

test:
	pytest backend/tests -q

docker-build:
	docker compose build

docker-ingest:
	docker compose run --rm app python -m backend.seed_data

docker-up:
	docker compose up

docker-down:
	docker compose down