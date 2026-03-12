# AI Standards

## Purpose
Operational standards for AI agents working in this repository.

## Change Standards
- Keep changes minimal, scoped, and reversible.
- Prefer updating existing code paths over creating parallel implementations.
- Remove dead code from superseded iterations.
- Keep docs low-maintenance and avoid duplicate sources of truth.
- When behavior changes, update code, tests, and canonical docs together.

## Documentation Standards
- Canonical human docs: `docs/core/`
- Temporary initiative docs: `docs/active/`
- AI support docs: `docs/ai/`
- Historical docs: `docs/archive/`
- Pending removal: `docs/deprecated/`

Do not point live links to deprecated files.

## Release Notes Standard
Use this format for production releases.

### Title Format
- `v<version> — <short focus>`

### Tag Convention
- `prod-v<version>`

### Required Section Order
1. `Summary`
2. `Highlights`
3. `Added`
4. `Changed`
5. `Fixed`
6. `Performance`
7. `Operations`
8. `Breaking Changes`
9. `Validation`
10. `Rollback`

### Template
```markdown
## v<version>

Tag: `prod-v<version>`
Promoted SHA: `<sha>`
Previous release: `prod-v<previous-version>`

### Summary
- ...

### Highlights
- ...

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Performance
- ...

### Operations
- ...

### Breaking Changes
- None.

### Validation
- `poetry run python scripts/validate/validate_prod_release.py` passed.
- Additional checks: ...

### Rollback
- Roll back to `prod-v<previous-version>` (or corresponding Fly release).
```
