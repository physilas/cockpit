.PHONY: build test

PYTHON ?= .venv/bin/python

build:
	$(PYTHON) build_pwa.py

test:
	$(PYTHON) -m unittest discover -s tests -v
