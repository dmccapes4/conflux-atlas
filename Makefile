# Conflux Atlas — root Makefile
# MakefileBook: mk/*.mk (imperative). Prefer bash — this machine is Linux.
SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -lc

include mk/00_main.mk
include mk/10_data.mk
include mk/90_verify.mk
