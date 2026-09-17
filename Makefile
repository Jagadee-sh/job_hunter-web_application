install:
	python -m pip install -e ".[dev]"
format:
	black backend tests
lint:
	ruff check backend tests
	mypy backend
test:
	pytest --cov=backend --cov-fail-under=90
run:
	uvicorn backend.main:app --reload
