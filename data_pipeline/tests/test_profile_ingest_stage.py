import json
from pathlib import Path

from scripts.data_pipeline import profile_ingest_stage as module


def test_extract_max_rss_kb_parses_value() -> None:
    stderr_text = "Maximum resident set size (kbytes): 12345"
    assert module.extract_max_rss_kb(stderr_text) == 12345


def test_extract_time_verbose_metrics_parses_core_fields() -> None:
    stderr_text = """
User time (seconds): 0.12
System time (seconds): 0.03
Percent of CPU this job got: 90%
Elapsed (wall clock) time (h:mm:ss or m:ss): 0:00.20
"""
    metrics = module.extract_time_verbose_metrics(stderr_text)
    assert metrics["user_time_seconds"] == "0.12"
    assert metrics["system_time_seconds"] == "0.03"
    assert metrics["cpu_percent"] == "90"
    assert metrics["elapsed_wall_time"] == "0:00.20"


def test_write_result_creates_function_timestamp_named_json(tmp_path: Path) -> None:
    run_data = {
        "started_at_utc": "2026-03-12T12:00:00+00:00",
        "duration_seconds": 1.234,
        "exit_code": 0,
        "stdout": "hello",
        "stderr": "Maximum resident set size (kbytes): 999",
        "max_rss_kb": 999,
        "time_verbose_metrics": {"user_time_seconds": "0.1"},
    }
    output_path = module.write_result(
        target_functions=["data_pipeline.src.ingest.get_ranks.main"],
        command=["python", "-m", "data_pipeline.src.ingest.get_ranks"],
        output_dir=tmp_path,
        run_data=run_data,
        max_output_chars=50,
    )
    assert output_path.name.startswith("get_ranks.")
    assert output_path.name.endswith(".json")
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["target_functions"] == ["data_pipeline.src.ingest.get_ranks.main"]
    assert (
        payload["profile_generator_function"]
        == "scripts.data_pipeline.profile_ingest_stage.run_profiled_command"
    )
    assert payload["command"] == ["python", "-m", "data_pipeline.src.ingest.get_ranks"]
    assert payload["started_at_utc"] == "2026-03-12T12:00:00+00:00"
    assert payload["duration_seconds"] == 1.234
    assert payload["stderr_tail"].endswith("999")
    assert payload["tails_pretty_lines"][0] == "=== STDOUT TAIL ==="
    assert "=== STDERR TAIL ===" in payload["tails_pretty_lines"]


def test_run_profiled_command_smoke() -> None:
    result = module.run_profiled_command(["python", "-c", "print('ok')"])
    assert result["exit_code"] == 0
    assert "ok" in result["stdout"]
    assert result["duration_seconds"] >= 0
