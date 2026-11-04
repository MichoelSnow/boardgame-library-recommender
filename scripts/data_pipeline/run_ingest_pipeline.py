#!/usr/bin/env python3
"""Run the full ingest pipeline with stage-aware retries and resume support."""

from __future__ import annotations

import argparse
import json
import logging
import os
import smtplib
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _default_log_dir() -> Path:
    log_dir_override = os.getenv("INGEST_LOG_DIR", "").strip()
    if log_dir_override:
        return Path(log_dir_override)
    return Path("/app/data/logs/ingest")


@dataclass(frozen=True)
class Stage:
    name: str
    command: list[str]


STAGES: tuple[Stage, ...] = (
    Stage(
        name="get_ranks",
        command=["poetry", "run", "python", "-m", "data_pipeline.src.ingest.get_ranks"],
    ),
    Stage(
        name="get_game_data",
        command=[
            "poetry",
            "run",
            "python",
            "-m",
            "data_pipeline.src.ingest.get_game_data",
            "--continue-from-last",
            "--save-every-n-batches",
            "20",
        ],
    ),
    Stage(
        name="get_ratings",
        command=[
            "poetry",
            "run",
            "python",
            "-m",
            "data_pipeline.src.ingest.get_ratings",
            "--continue-from-last",
        ],
    ),
)

STAGE_PREREQUISITES: dict[str, str] = {
    "get_game_data": "get_ranks",
    "get_ratings": "get_game_data",
}


def _default_state_path() -> Path:
    state_override = os.getenv("INGEST_RUN_STATE_PATH", "").strip()
    if state_override:
        return Path(state_override)
    return Path("/app/data/ingest/run_state.json")


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    with state_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_initial_state(
    *, include_ratings: bool, run_log_path: str | None = None
) -> dict[str, Any]:
    stage_names = [
        stage.name for stage in STAGES if include_ratings or stage.name != "get_ratings"
    ]
    stage_records = {
        stage_name: {
            "status": "pending",
            "attempts": 0,
            "last_attempt_started_at_utc": None,
            "last_attempt_finished_at_utc": None,
            "last_error": None,
        }
        for stage_name in stage_names
    }
    now = _utc_now_iso()
    return {
        "schema_version": 1,
        "status": "running",
        "started_at_utc": now,
        "updated_at_utc": now,
        "completed_at_utc": None,
        "failed_at_utc": None,
        "run_log_path": run_log_path,
        "stages": stage_records,
    }


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at_utc"] = _utc_now_iso()
    with state_path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def _selected_stages(
    include_ratings: bool,
    *,
    continue_game_data: bool = True,
    only_stage: str | None = None,
) -> list[Stage]:
    stages = list(STAGES)
    if not continue_game_data:
        game_data_stage = next(
            stage for stage in stages if stage.name == "get_game_data"
        )
        fresh_game_data_command = [
            argument
            for argument in game_data_stage.command
            if argument != "--continue-from-last"
        ]
        stages = [
            Stage(name=stage.name, command=fresh_game_data_command)
            if stage is game_data_stage
            else stage
            for stage in stages
        ]
    selected = [
        stage for stage in stages if include_ratings or stage.name != "get_ratings"
    ]
    if only_stage is not None:
        selected = [stage for stage in selected if stage.name == only_stage]
    return selected


def _next_incomplete_stage(state: dict[str, Any], stages: list[Stage]) -> Stage | None:
    stage_state = state.get("stages", {})
    for stage in stages:
        if stage_state.get(stage.name, {}).get("status") != "completed":
            return stage
    return None


def _validate_stage_prerequisite(state: dict[str, Any], *, stage_name: str) -> None:
    prerequisite = STAGE_PREREQUISITES.get(stage_name)
    if prerequisite is None:
        return
    prerequisite_status = state.get("stages", {}).get(prerequisite, {}).get("status")
    if prerequisite_status != "completed":
        raise ValueError(
            f"{stage_name} requires {prerequisite} to be completed; "
            f"current status is {prerequisite_status or 'missing'}"
        )


def _should_start_new_run(existing_state: dict[str, Any], *, reset_state: bool) -> bool:
    """Start fresh after completion, but resume an interrupted run by default."""
    return (
        reset_state or not existing_state or existing_state.get("status") == "completed"
    )


def _cleanup_superseded_ingest_artifacts(ingest_dir: Path) -> list[Path]:
    """Retain only the latest ranks and game-data artifacts."""
    game_data_dir = ingest_dir / "game_data"
    ranks_dir = ingest_dir / "ranks"
    game_data_files = sorted(
        game_data_dir.glob("boardgame_data_*.duckdb"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    latest_game_data = game_data_files[0] if game_data_files else None
    removed_files: list[Path] = []
    files_to_remove = game_data_files[1:]
    wal_files = list(game_data_dir.glob("boardgame_data_*.duckdb.wal"))
    if latest_game_data is None:
        files_to_remove.extend(wal_files)
    else:
        files_to_remove.extend(
            wal_file
            for wal_file in wal_files
            if wal_file.name != f"{latest_game_data.name}.wal"
        )
    for old_file in files_to_remove:
        try:
            old_file.unlink()
        except OSError:
            logger.warning("Unable to remove superseded ingest artifact: %s", old_file)
            continue
        removed_files.append(old_file)
        logger.info("Removed superseded ingest artifact: %s", old_file)

    rank_files = sorted(
        ranks_dir.glob("boardgame_ranks_*.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_rank_file in rank_files[1:]:
        try:
            old_rank_file.unlink()
        except OSError:
            logger.warning(
                "Unable to remove superseded ingest artifact: %s", old_rank_file
            )
            continue
        removed_files.append(old_rank_file)
        logger.info("Removed superseded ingest artifact: %s", old_rank_file)
    return removed_files


def _send_email_notification(subject: str, body: str) -> bool:
    to_raw = os.getenv("INGEST_NOTIFY_EMAIL_TO", "").strip()
    from_email = os.getenv("INGEST_NOTIFY_EMAIL_FROM", "").strip()
    smtp_host = os.getenv("INGEST_NOTIFY_SMTP_HOST", "").strip()
    if not to_raw or not from_email or not smtp_host:
        logger.info(
            "Email notification skipped; set INGEST_NOTIFY_EMAIL_TO, "
            "INGEST_NOTIFY_EMAIL_FROM, and INGEST_NOTIFY_SMTP_HOST to enable."
        )
        return False

    smtp_port = int(os.getenv("INGEST_NOTIFY_SMTP_PORT", "587").strip())
    username = os.getenv("INGEST_NOTIFY_SMTP_USERNAME", "").strip()
    password = os.getenv("INGEST_NOTIFY_SMTP_PASSWORD", "").strip()
    use_starttls = os.getenv("INGEST_NOTIFY_SMTP_STARTTLS", "true").lower() == "true"
    recipients = [entry.strip() for entry in to_raw.split(",") if entry.strip()]
    if not recipients:
        logger.warning("Email notification skipped; recipient list is empty.")
        return False

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = ", ".join(recipients)
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host=smtp_host, port=smtp_port, timeout=30) as smtp:
        if use_starttls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)
    logger.info("Sent notification email to %s", ", ".join(recipients))
    return True


def _notify(event: str, state: dict[str, Any], stage_name: str | None = None) -> None:
    app_name = os.getenv("FLY_APP_NAME", "bg-lib-ingest")
    subject = f"[{app_name}] ingest pipeline {event}"
    lines = [
        f"App: {app_name}",
        f"Event: {event}",
        f"Timestamp (UTC): {_utc_now_iso()}",
        f"State status: {state.get('status', 'unknown')}",
    ]
    if stage_name:
        lines.append(f"Stage: {stage_name}")
    lines.append("")
    lines.append("Run state:")
    lines.append(json.dumps(state, indent=2, sort_keys=True))
    try:
        _send_email_notification(subject=subject, body="\n".join(lines))
    except Exception as exc:
        logger.exception("Failed to send notification: %s", exc)


def _run_stage(stage: Stage) -> int:
    logger.info("Running stage %s: %s", stage.name, " ".join(stage.command))
    with subprocess.Popen(
        stage.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as process:
        assert process.stdout is not None
        for line in process.stdout:
            logger.info("[%s] %s", stage.name, line.rstrip())
        return process.wait()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run ingest pipeline stages with retries and resume support."
    )
    parser.add_argument(
        "--state-path",
        type=Path,
        default=_default_state_path(),
        help="Path to run state JSON (default: INGEST_RUN_STATE_PATH or /app/data/ingest/run_state.json).",
    )
    parser.add_argument(
        "--max-stage-attempts",
        type=int,
        default=int(os.getenv("INGEST_MAX_STAGE_ATTEMPTS", "3")),
        help="Maximum attempts per stage before run is marked failed.",
    )
    parser.add_argument(
        "--retry-delay-seconds",
        type=int,
        default=int(os.getenv("INGEST_RETRY_DELAY_SECONDS", "30")),
        help="Delay before retrying a failed stage.",
    )
    parser.add_argument(
        "--skip-ratings",
        action="store_true",
        help="Skip get_ratings stage.",
    )
    parser.add_argument(
        "--only-stage",
        choices=[stage.name for stage in STAGES],
        help="Run only the selected stage using the existing run state.",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Ignore existing state and start a fresh run state.",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=_default_log_dir(),
        help="Directory for run log files (default: INGEST_LOG_DIR or /app/data/logs/ingest).",
    )
    return parser.parse_args()


def _setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = (
        log_dir
        / f"run_ingest_pipeline_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.log"
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(os.getenv("INGEST_LOG_LEVEL", "INFO"))
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(run_log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    return run_log_path


def _maintenance_mode_enabled() -> bool:
    return os.getenv("INGEST_MAINTENANCE_MODE", "false").lower() == "true"


def _maintenance_deadline() -> datetime | None:
    raw_deadline = os.getenv("INGEST_MAINTENANCE_UNTIL_UTC", "").strip()
    if not raw_deadline:
        return None
    try:
        deadline = datetime.fromisoformat(raw_deadline.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "INGEST_MAINTENANCE_UNTIL_UTC must be an ISO-8601 UTC timestamp"
        ) from exc
    if deadline.tzinfo is None:
        raise ValueError("INGEST_MAINTENANCE_UNTIL_UTC must include a timezone")
    return deadline.astimezone(UTC)


def _enter_maintenance_mode() -> int:
    try:
        deadline = _maintenance_deadline()
    except ValueError:
        logger.exception(
            "Invalid maintenance lease; refusing indefinite maintenance mode."
        )
        return 1
    if deadline is None:
        logger.error(
            "INGEST_MAINTENANCE_MODE=true but no maintenance lease was supplied; "
            "refusing indefinite maintenance mode."
        )
        return 1

    logger.warning(
        "INGEST_MAINTENANCE_MODE=true; keeping machine alive for manual commands "
        "until %s.",
        deadline.isoformat(),
    )
    logger.warning("Pipeline stages will not run until maintenance mode is disabled.")
    while True:
        remaining_seconds = (deadline - datetime.now(UTC)).total_seconds()
        if remaining_seconds <= 0:
            logger.warning("Maintenance lease expired; stopping the ingestion machine.")
            return 0
        time.sleep(min(60, remaining_seconds))


def _notify_and_reset_max_attempt_stage(
    *,
    state: dict[str, Any],
    state_path: Path,
    stage_name: str,
    reason: str,
) -> int:
    stage_state = state["stages"][stage_name]
    prior_attempts = int(stage_state.get("attempts", 0))

    state["status"] = "failed"
    state["failed_at_utc"] = _utc_now_iso()
    stage_state["status"] = "failed"
    stage_state["attempts"] = 0
    stage_state["last_error"] = reason
    stage_state["last_failure_notified_at_utc"] = _utc_now_iso()

    _save_state(state_path, state)
    _notify(event="failed_max_attempts", state=state, stage_name=stage_name)
    logger.error(
        "Stage %s reached max attempts (%d). Alert sent; stage remains failed "
        "until a later run retries it.",
        stage_name,
        prior_attempts,
    )
    return 1


def main() -> int:
    args = parse_args()
    run_log_path = _setup_logging(args.log_dir)
    logger.info("Writing ingest run log to %s", run_log_path)
    logger.info("Invocation: %s", " ".join([sys.executable, *sys.argv]))
    if _maintenance_mode_enabled():
        return _enter_maintenance_mode()
    if args.max_stage_attempts < 1:
        raise ValueError("--max-stage-attempts must be >= 1")

    include_ratings = not args.skip_ratings
    existing_state = _load_state(args.state_path)
    if args.only_stage and args.reset_state:
        raise ValueError("--only-stage cannot be combined with --reset-state")
    if args.only_stage and not existing_state:
        if args.only_stage != "get_ranks":
            raise ValueError(
                f"--only-stage {args.only_stage} requires an existing run state"
            )
        existing_state = _build_initial_state(
            include_ratings=True, run_log_path=str(run_log_path)
        )
    start_new_run = (
        False
        if args.only_stage
        else _should_start_new_run(existing_state, reset_state=args.reset_state)
    )
    selected_stages = _selected_stages(
        include_ratings=include_ratings,
        continue_game_data=not start_new_run,
        only_stage=args.only_stage,
    )
    if start_new_run:
        state = _build_initial_state(
            include_ratings=include_ratings, run_log_path=str(run_log_path)
        )
        _save_state(args.state_path, state)
    else:
        state = existing_state
        if args.only_stage:
            _validate_stage_prerequisite(state, stage_name=args.only_stage)
            stage_state = state["stages"][args.only_stage]
            stage_state["status"] = "pending"
            stage_state["attempts"] = 0
            stage_state["last_error"] = None
            state["status"] = "running"
            state["completed_at_utc"] = None
            state["failed_at_utc"] = None
        state["run_log_path"] = str(run_log_path)
        _save_state(args.state_path, state)

    logger.info("Using state file: %s", args.state_path)
    logger.info("Selected stages: %s", [stage.name for stage in selected_stages])

    while True:
        stage = _next_incomplete_stage(state, selected_stages)
        if stage is None:
            all_stages_completed = all(
                stage_state.get("status") == "completed"
                for stage_state in state.get("stages", {}).values()
            )
            if all_stages_completed:
                state["status"] = "completed"
                state["completed_at_utc"] = _utc_now_iso()
            elif args.only_stage:
                state["status"] = "running"
                state["completed_at_utc"] = None
            _save_state(args.state_path, state)
            if all_stages_completed:
                _notify(event="completed", state=state)
                logger.info("Ingest pipeline completed successfully.")
            else:
                _notify(
                    event="stage_completed", state=state, stage_name=args.only_stage
                )
                logger.info("Requested stage completed successfully.")
            return 0

        stage_state = state["stages"][stage.name]
        attempts = int(stage_state.get("attempts", 0))
        if attempts >= args.max_stage_attempts:
            return _notify_and_reset_max_attempt_stage(
                state=state,
                state_path=args.state_path,
                stage_name=stage.name,
                reason=(
                    f"max_attempts_reached_pre_run (limit={args.max_stage_attempts})"
                ),
            )

        stage_state["status"] = "running"
        stage_state["attempts"] = attempts + 1
        stage_state["last_attempt_started_at_utc"] = _utc_now_iso()
        stage_state["last_error"] = None
        _save_state(args.state_path, state)

        result_code = _run_stage(stage)
        stage_state["last_attempt_finished_at_utc"] = _utc_now_iso()
        if result_code == 0:
            stage_state["status"] = "completed"
            _save_state(args.state_path, state)
            logger.info("Stage %s completed.", stage.name)
            if stage.name == "get_game_data":
                _cleanup_superseded_ingest_artifacts(
                    Path(__file__).resolve().parents[2] / "data" / "ingest"
                )
            continue

        stage_state["status"] = "failed"
        stage_state["last_error"] = f"exit_code={result_code}"
        _save_state(args.state_path, state)
        logger.error(
            "Stage %s failed on attempt %d/%d.",
            stage.name,
            stage_state["attempts"],
            args.max_stage_attempts,
        )
        if stage_state["attempts"] >= args.max_stage_attempts:
            return _notify_and_reset_max_attempt_stage(
                state=state,
                state_path=args.state_path,
                stage_name=stage.name,
                reason=(
                    f"max_attempts_reached_post_failure (limit={args.max_stage_attempts})"
                ),
            )
        logger.info(
            "Retrying stage %s in %d seconds.", stage.name, args.retry_delay_seconds
        )
        time.sleep(args.retry_delay_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
