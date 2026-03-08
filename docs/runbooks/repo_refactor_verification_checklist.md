# Repository Refactor Verification Checklist

Use this checklist after major path or package refactors.

## 1. Repository Hygiene
- [ ] No unexpected local artifacts in moved directories (`__pycache__`, `.ipynb_checkpoints`, temp backups).
- [ ] `.gitignore` still blocks generated artifacts and temp files.
- [ ] Top-level structure in root `README.md` matches actual directories.

## 2. Import and Packaging Integrity
- [ ] Python package metadata reflects the new package names/paths (`pyproject.toml`).
- [ ] Deprecated compatibility shims exist only where needed and are clearly marked.
- [ ] No internal references remain to removed module paths.

Validation command:
```bash
poetry run python -m compileall backend data_pipeline
```

## 3. Workflow and CI References
- [ ] CI paths (`black`, `compileall`, `pytest`) use current directory/package names.
- [ ] Any deploy/ops workflows referencing moved files are updated.

Validation command:
```bash
rg -n "crawler/|crawler/src|crawler/tests|python crawler|from crawler|import crawler" .github docs scripts README.md pyproject.toml
```

## 4. Documentation and Runbooks
- [ ] Directory READMEs describe the new structure and command entry points.
- [ ] Root README command examples use current paths and invocation style.
- [ ] ADR/policy docs reflect the new naming decision and rationale.

## 5. Functional Smoke Checks
- [ ] Pipeline module commands resolve and start argument parsing correctly.
- [ ] Existing runtime/deploy validation scripts still run.

Suggested smoke commands:
```bash
poetry run python -c "import data_pipeline.src.ingest.get_ranks, data_pipeline.src.ingest.get_game_data, data_pipeline.src.ingest.get_ratings, data_pipeline.src.transform.data_processor, data_pipeline.src.features.create_embeddings"
```

## 6. Commit Readiness
- [ ] `git status` shows only intentional move/update/shim changes.
- [ ] Release/versioning decision confirmed (no version bump for docs/structure-only work).
- [ ] PR description includes migration notes for any temporary shims.
