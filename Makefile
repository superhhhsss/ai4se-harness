.PHONY: test lint install cov demo

install:
	pip install -e .

test:
	pytest tests/ -v

lint:
	flake8 src/ --max-line-length=120

cov:
	pytest tests/ -v --cov=ai4se_harness --cov-report=term

demo:
	pytest tests/test_demo.py -v