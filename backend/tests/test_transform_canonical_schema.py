from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_PATH = ROOT / "scripts" / "db" / "transform_canonical_schema.py"
SPEC = spec_from_file_location("transform_canonical_schema", MODULE_PATH)
MODULE = module_from_spec(SPEC)
assert SPEC is not None
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

transform_schema = MODULE.transform_schema


def test_transform_schema_renames_legacy_pax_games_objects():
    input_sql = """
CREATE TABLE public.pax_games (id integer NOT NULL, bgg_id integer);
CREATE SEQUENCE public.pax_games_id_seq;
ALTER TABLE ONLY public.pax_games ADD CONSTRAINT pax_games_pkey PRIMARY KEY (id);
CREATE INDEX ix_pax_games_bgg_id ON public.pax_games USING btree (bgg_id);
ALTER TABLE ONLY public.pax_games ADD CONSTRAINT pax_games_bgg_id_fkey FOREIGN KEY (bgg_id) REFERENCES public.games(id);
"""
    output_sql = transform_schema(input_sql)

    assert "public.pax_games" not in output_sql
    assert "pax_games_id_seq" not in output_sql
    assert "pax_games_pkey" not in output_sql
    assert "ix_pax_games_bgg_id" not in output_sql
    assert "pax_games_bgg_id_fkey" not in output_sql
    assert "public.library_games" in output_sql
    assert "library_games_id_seq" in output_sql
    assert "library_games_pkey" in output_sql
    assert "ix_library_games_bgg_id" in output_sql
    assert "library_games_bgg_id_fkey" in output_sql
