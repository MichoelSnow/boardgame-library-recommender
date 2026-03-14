#!/usr/bin/env python3

import argparse
import logging
import re
from pathlib import Path

LOGGER = logging.getLogger(__name__)


REPLACEMENTS = [
    (r"\bpublic\.pax_games\b", "public.library_games"),
    (r"\bpax_games_id_seq\b", "library_games_id_seq"),
    (r"\bpax_games_pkey\b", "library_games_pkey"),
    (r"\bix_pax_games_bgg_id\b", "ix_library_games_bgg_id"),
    (r"\bpax_games_bgg_id_fkey\b", "library_games_bgg_id_fkey"),
]


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def transform_schema(sql_text: str) -> str:
    transformed = sql_text
    for pattern, replacement in REPLACEMENTS:
        transformed = re.sub(pattern, replacement, transformed)
    return transformed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform canonical schema SQL from legacy pax_games naming to library_games naming."
    )
    parser.add_argument(
        "--input",
        default=".tmp/canonical_prod_schema.sql",
        help="Input canonical schema SQL file.",
    )
    parser.add_argument(
        "--output",
        default=".tmp/canonical_repo_schema.sql",
        help="Output transformed schema SQL file.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input schema file not found: {input_path}")
    input_text = input_path.read_text(encoding="utf-8")
    if not input_text.strip():
        raise RuntimeError(f"Input schema file is empty: {input_path}")

    transformed_text = transform_schema(input_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(transformed_text, encoding="utf-8")
    LOGGER.info("Wrote transformed schema file: %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
