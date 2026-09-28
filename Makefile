.PHONY: up down demo ingest enrich search eval test lint install
up:
	docker compose up --build -d --wait
down:
	docker compose down
ingest:
	docker compose exec -T api catalog ingest
enrich:
	docker compose exec -T api catalog enrich
search:
	docker compose exec -T api catalog search 'monthly recurring revenue' --kind table
eval:
	docker compose exec -T api catalog eval
	mkdir -p reports
	docker compose cp api:/app/reports/eval.json reports/eval.json
test:
	docker compose exec -T api pytest -q
lint:
	docker compose exec -T api ruff check catalog tests
demo: up ingest enrich search eval
install:
	uv sync --extra dev --frozen
	cd ui && npm ci
