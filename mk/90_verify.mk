# ===============================
# 90_verify.mk — data infrastructure validation
# ===============================
# Markdown reports only (no PDF). Sibling spirit: 2OPMD mk/90_reports.mk

VALIDATION_DIR ?= data-validation-reports

.PHONY: reports-dir verify-all verify-data shape-report phase0-reports test test-network test-phase1 test-phase2 test-phase3 phase2-5 phase1-scorecard phase2-trust phase3-backtest phase3-bridge beacon-pdfs beacon-tranche1 phase2b

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

test-phase1: ## Phase 1 contracts only, with skip reasons (-rs) while unimplemented
	@$(PY) -m pytest -q -rs -m phase1; rc=$$?; \
	if [ $$rc -eq 5 ]; then echo "(phase1 modules not implemented yet — contracts all skipped)"; exit 0; fi; \
	exit $$rc

test-phase2: ## Phase 2 contracts only, with skip reasons (-rs) while unimplemented
	@$(PY) -m pytest -q -rs -m phase2; rc=$$?; \
	if [ $$rc -eq 5 ]; then echo "(phase2 modules not implemented yet — contracts all skipped)"; exit 0; fi; \
	exit $$rc

test-phase3: ## Phase 3 contracts only, with skip reasons (-rs) while unimplemented
	@$(PY) -m pytest -q -rs -m phase3; rc=$$?; \
	if [ $$rc -eq 5 ]; then echo "(phase3 modules not implemented yet — contracts all skipped)"; exit 0; fi; \
	exit $$rc

phase2-5: reports-dir ## Expanded source ledger + PortalGC sweep → data-validation-reports/PHASE2_5_*.json
	@$(PY) scripts/run_phase2_5_expansion.py

phase1-scorecard: ## Run LOPO scorecard → data-validation-reports/PHASE1_SCORECARD.json
	@$(PY) scripts/run_phase1_scorecard.py

phase2-trust: ## Run 1975-cut + source corroboration → PHASE2_TRUST.json
	@$(PY) scripts/run_phase2_trust.py

phase3-backtest: reports-dir ## Pre-registered 1975 banded backtest → PHASE3_BACKTEST.json
	@$(PY) scripts/run_phase3_backtest.py

phase3-bridge: reports-dir ## 1920+ dynamics backfill + holdout settle → PHASE3_BRIDGE.json
	@$(PY) scripts/run_phase3_bridge.py

beacon-tranche1: reports-dir ## Fetch/ingest UNHCR SYR OD + upsert Syria/Lebanon/Iran events+edges
	@$(PY) scripts/fetch_unhcr_coo.py
	@$(PY) scripts/ingest_unhcr_coo.py
	@$(PY) scripts/seed_beacon_tranche1.py

beacon-pdfs: ## Download open PDFs listed in docs/beacon-inventories/ → data/raw/beacons/
	@$(PY) scripts/download_beacon_pdfs.py --continue

phase2b: reports-dir ## Deterministic connascence layer → PHASE2B_*.json
	@$(PY) scripts/run_phase2b_connascence.py

test-network: ## Opt-in live URL probes (scrapers/APIs may 404/rotate)
	@env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
		$(PY) -m pytest -q -m network
