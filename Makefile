PYTHON ?= python
VENV ?= .venv

ifeq ($(OS),Windows_NT)
VENV_PYTHON := $(VENV)/Scripts/python.exe
VENV_PIP := $(VENV)/Scripts/pip.exe
else
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip
endif

.PHONY: venv install run test

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(VENV_PIP) install -r requirements.txt
	$(VENV_PIP) install -e .

run:
	$(VENV_PYTHON) -m witness_forge.cli chat

test:
	$(VENV_PYTHON) -m pytest
