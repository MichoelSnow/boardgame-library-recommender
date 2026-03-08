# Release Notes Standard

## Purpose
- Standardize release note format across all production releases.
- Keep release communication consistent, comparable, and audit-friendly.

## Scope
- Applies to every production app version release (for example `0.3.0`).
- Use this format for Git tags/releases in GitHub.

## Title Format
- `v<version> — <short focus>`
- Example:
  - `v0.3.0 — Runtime, Postgres Lifecycle, and Alerting Hardening`

## Tag Convention
- Canonical production tag format:
  - `prod-v<version>`
- Example:
  - `prod-v0.3.0`

## Required Sections (Use In This Exact Order)
1. `Summary`
- 2-4 bullets of the most important outcomes.

2. `Highlights`
- 3-6 bullets for major user-visible or operationally significant changes.

3. `Added`
- New features, endpoints, workflows, scripts, or runbooks.

4. `Changed`
- Behavior changes, architecture/runtime updates, or policy updates.

5. `Fixed`
- Bug fixes, regressions, edge-case handling fixes.

6. `Performance`
- Throughput/latency improvements, scalability changes, benchmark outcomes.

7. `Operations`
- Deploy/runbook/alerting/observability/infra changes.

8. `Breaking Changes`
- State `None.` when not applicable.
- If present, include migration/compatibility guidance.

9. `Validation`
- Required checks run and pass status.
- Include concrete evidence references (scripts/checklists), not raw logs.

10. `Rollback`
- One-line rollback target guidance (tag/release linkage).

## Style Rules
- Use concise bullets; no prose paragraphs longer than 2-3 lines.
- Prefer outcome-first wording.
- Avoid implementation minutiae unless needed for risk/compatibility.
- Keep tense consistent (`Added`, `Updated`, `Fixed`).
- Always include:
  - version
  - release tag
  - commit SHA (or exact promoted SHA)
  - previous release tag

## Release Notes Template
```markdown
## v<version>

Tag: `prod-v<version>`  
Promoted SHA: `<sha>`  
Previous release: `prod-v<previous-version>`

### Summary
- ...
- ...

### Highlights
- ...
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
- Roll back to `prod-v<previous-version>` (or corresponding Fly release) per deploy runbook.
```
