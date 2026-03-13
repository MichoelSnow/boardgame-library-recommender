# Notebooks Guide

## Purpose
- Notebooks are for exploration and reference, not canonical production execution.
- Canonical production logic lives under `data_pipeline/src/`.

## Hardening Rules
- Never store secrets, passwords, tokens, or API keys in notebook source or outputs.
- Load credentials only from environment variables.
- Keep notebook outputs cleared before commit.
- Keep generated data artifacts out of `data_pipeline/notebooks/`; store them under `data/ingest/` or `data/transform/processed/`.
- Update stale path/import references to current conventions when touching notebooks:
  - use `data/ingest/...` and `data/transform/processed/...` (not `data/crawler/...`)
  - use `data_pipeline.src...` for imports (not `crawler.src...`)

## Archive Policy
- Archived notebooks are not kept in this repository.
- Do not add new active work there.
- If you need to continue a historical investigation, copy the notebook into the main notebooks directory first.
