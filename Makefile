.PHONY: setup data check test evals clean

PY := python

setup:
	$(PY) -m pip install -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo "Now put your ANTHROPIC_API_KEY in .env"

data:
	$(PY) scripts/gen/generate.py
	$(PY) scripts/gen/make_binaries.py

check:
	PYTHONPATH=src $(PY) -c "from insighthub.config import check; check()"

test:
	PYTHONPATH=src $(PY) -m pytest tests -q

evals:
	PYTHONPATH=src $(PY) -m insighthub.evals.run --suite all --split dev

clean:
	rm -rf index runs traces .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
