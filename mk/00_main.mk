# ===============================
# Conflux Atlas — 00_main.mk
# ===============================
# MakefileBook: data ingest, demo, validation reports.
# Sibling pattern: 2OPMD/2ndOpinionMD/mk/ (trimmed; bash not zsh).

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -lc

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
export PYTHONPATH := $(ROOT)

PY ?= $(shell if [ -x "$(ROOT)/.venv/bin/python" ]; then echo "$(ROOT)/.venv/bin/python"; \
	elif [ -x "$(ROOT)/venv/bin/python" ]; then echo "$(ROOT)/venv/bin/python"; \
	else command -v python3; fi)

.PHONY: help smoke demo env-doctor

help: ## List MakefileBook targets
	@grep -hE '^[a-zA-Z0-9_\-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}' | sort -u

env-doctor: ## Show python + key paths
	@echo "=== CONFLUX ENV ==="; \
	echo "ROOT=$$(pwd)"; \
	echo -n "PY:     "; command -v "$(PY)" || echo missing; \
	"$(PY)" -c 'import sys; print("python:", sys.version.split()[0])'; \
	echo -n "processed: "; ls data/processed/*.jsonl 2>/dev/null | wc -l; \
	echo -n "bib:      "; test -f data/sources/BIBLIOGRAPHY.md && echo ok || echo missing

smoke: ## Run pygame demo smoke (--smoke)
	@$(PY) main.py --smoke

demo: ## Run interactive pygame demo
	@$(PY) main.py
