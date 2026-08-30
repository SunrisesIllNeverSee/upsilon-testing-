.PHONY: db test ingest

db:
	docker compose up -d

test:
	pytest -q

ingest:
	python sec_ingest.py batch --issuers issuers.csv --start-year 2015 --end-year 2025 --out data/raw
