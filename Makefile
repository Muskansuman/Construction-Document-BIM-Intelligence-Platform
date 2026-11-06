.PHONY: install dev test lint api ui up sample

install:        ## full install (OCR, BIM, UI)
	pip install -r requirements.txt

dev:            ## lightweight install for tests
	pip install -r requirements-dev.txt

test:
	pytest --cov=app

lint:
	ruff check app tests

api:
	uvicorn app.main:app --reload --port 8000

ui:
	streamlit run frontend/streamlit_app.py

up:
	docker compose up --build

sample:         ## download a public IFC sample model
	bash scripts/download_sample_ifc.sh
