# PAX labeling tools

These scripts label and reconcile PAX library titles against BoardGameGeek
(BGG) records. They are analyst-facing tools, not stages of the general data
ingest pipeline.

## Choose the workflow

### Existing library/title corrections

Use this when an existing title record already has a title ID, library game
information, and possibly an incorrect BGG ID.

```text
existing-title CSV
    -> resolve_existing_pax_titles.py
       resolved CSV + review queue
    -> manual review / optional overrides
    -> finalize_pax_title_corrections.py
       cleaned library export
```

The resolver requires these input columns:

`title`, `title_id`, `game`, `game_barcode`, `publisher_name`, `bgg_id`,
`game_year`, and `status`.

Its default input format is pipe-delimited `cp1252`; use `--input-sep` and
`--input-encoding` for other files. BGG reference files are always supplied
explicitly with `--ranks`, `--first-publishers`, `--all-publishers`, and
`--versions`.

Example:

```bash
poetry run python scripts/pax_labeling/resolve_existing_pax_titles.py \
  --input data/pax/title_corrections_raw.csv \
  --ranks data/ingest/ranks/boardgame_ranks.csv \
  --first-publishers data/ingest/game_data/first_publishers.csv \
  --all-publishers data/transform/processed/latest/boardgamepublishers.csv \
  --versions data/transform/processed/latest/versions.csv \
  --output data/pax/title_corrections_with_new_bgg_id.csv \
  --review-output data/pax/title_corrections_review_top3.csv
```

Optional resolver inputs are `--manual-fixes`, `--prior-map`, and
`--excluded-title-ids`. Manual fixes may map `title_id`/`min_titles_id` or an
existing BGG ID to `bgg_id`/`new_bgg_id`.

Finalize the reviewed resolver output with:

```bash
poetry run python scripts/pax_labeling/finalize_pax_title_corrections.py \
  --input data/pax/title_corrections_with_new_bgg_id.csv \
  --output data/pax/title_corrections_cleaned.csv
```

Optional finalization inputs are `--manual-fixes`, `--keep-name`, and
`--ranks`. The finalizer preserves the existing confidence/status policy and
emits the established cleaned columns: `title`, `title_id`, `game`,
`game_barcode`, `bgg_id`, `match`, `has_updated_title`, `title_original`,
`has_updated_bgg_id`, and `bgg_id_original`.

### New game intake

Use this for a new-game CSV that has not yet been matched to BGG. The input
requires only `title` and `publisher_name`; extra columns are preserved only
in the input and are not copied to the compact output. The default input
format is comma-delimited UTF-8.

```bash
poetry run python scripts/pax_labeling/match_new_pax_games.py \
  --input data/pax/new_games.csv \
  --output data/pax/new_games_matched.csv \
  --ranks data/ingest/ranks/boardgame_ranks.csv \
  --first-publishers data/ingest/game_data/first_publishers.csv \
  --all-publishers data/transform/processed/latest/boardgamepublishers.csv \
  --versions data/transform/processed/latest/versions.csv
```

This produces one best-match row per input row with `title`,
`publisher_name`, `bgg_id`, `bgg_name`, `bgg_publishers`, and
`year_published`. It has no review queue and does not apply the existing-title
workflow's manual/prior/exclusion inputs.

## Review and downstream use

The resolver's review CSV is the human review queue. Inspect low-confidence,
ambiguous, and changed-ID rows before finalization; put durable corrections in
the manual-fixes input rather than editing generated outputs.

The companion notebook [`data_pipeline/notebooks/clean_paxtt_data.ipynb`](../../data_pipeline/notebooks/clean_paxtt_data.ipynb)
contains historical manual corrections and matching diagnostics. It is for
review and investigation; the scripts above are the canonical workflow.

These tools write analyst CSVs. No repository process automatically consumes
their outputs. If a cleaned file is later imported into the backend, convert it
to the backend library-import contract (pipe-delimited CSV with a `bgg_id`
column) and follow the applicable data import documentation.
