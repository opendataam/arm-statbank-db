# Common tasks. Override PARSER_DIR to point at a statbank-parser checkout.
PARSER_DIR ?= ../statbank-parser
PY ?= .venv/bin/python
CLI = $(PY) -m armstat_db --parser-dir $(PARSER_DIR)

.PHONY: install fetch collect build validate docs test all clean

install:            ## create the virtual environment and install the package
	uv venv .venv && uv pip install -e '.[dev,translate]'

fetch:              ## download Armenian metadata and navigation trees from the PXWeb API
	$(CLI) fetch

collect:            ## list texts missing from the translation memory
	$(CLI) collect

translate:          ## machine-translate pending texts (needs ANTHROPIC_API_KEY)
	$(CLI) translate

build:              ## build build/armstat.duckdb
	$(CLI) build

validate:           ## consistency checks
	$(CLI) validate

docs:               ## regenerate docs/*/catalog.md
	$(CLI) docs

test:
	$(PY) -m pytest -q

all: build validate docs

clean:
	rm -rf build
