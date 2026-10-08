.PHONY: build test

PYTHON ?= .venv/bin/python

build:
	$(PYTHON) build.py

test:
	$(PYTHON) -m unittest discover -s tests -v
