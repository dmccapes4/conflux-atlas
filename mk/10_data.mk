# ===============================
# 10_data.mk — ingest / seed helpers
# ===============================

.PHONY: seed-events seed-edges list-processed

seed-events: ## Re-seed events.jsonl (3 demo triggers)
	@$(PY) scripts/seed_events.py

seed-edges: ## Re-seed edges.jsonl
	@$(PY) scripts/seed_migration_edges.py

list-processed: ## List processed JSONL with line counts
	@cd data/processed && wc -l *.jsonl | sort -n
