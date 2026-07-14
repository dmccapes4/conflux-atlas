# ===============================
# 90_verify.mk — data infrastructure validation
# ===============================
# Markdown reports only (no PDF). Sibling spirit: 2OPMD mk/90_reports.mk

VALIDATION_DIR ?= data-validation-reports

.PHONY: reports-dir verify-all verify-data shape-report phase0-reports test test-network

reports-dir:
	@mkdir -p "$(VALIDATION_DIR)"

verify-data: reports-dir ## Alias: run data infrastructure checks
	@$(PY) scripts/verify_data_infrastructure.py --out-dir "$(VALIDATION_DIR)"

verify-all: reports-dir ## Validate processed data → data-validation-reports/*.md
	@echo ">>> verify-all (data infrastructure)"
	@$(PY) scripts/verify_data_infrastructure.py --out-dir "$(VALIDATION_DIR)"
	@echo ">>> latest report:"
	@ls -lh "$(VALIDATION_DIR)/VERIFY_LATEST.md" 2>/dev/null || true

phase0-reports: ## Write docs/SHAPE_OF_THE_DATA.md + INTER_ANCHOR_VELOCITY.md
	@$(PY) scripts/report_shape_and_velocity.py

shape-report: verify-all phase0-reports ## Verify report + committed shape/velocity docs
	@echo "(also see docs/SHAPE_OF_THE_DATA.md and docs/INTER_ANCHOR_VELOCITY.md)"

test: ## Phase 0 pytest gate (offline; skips -m network)
	@$(PY) -m pytest -q -m "not network"

test-network: ## Opt-in live URL probes (scrapers/APIs may 404/rotate)
	@env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
		$(PY) -m pytest -q -m network
