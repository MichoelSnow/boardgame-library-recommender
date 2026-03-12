#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

try:
    from validation_common import (
        build_url,
        fetch_json,
    )
except ModuleNotFoundError:
    from scripts.validation_common import (
        build_url,
        fetch_json,
    )

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
DEFAULT_ALERT_STATE_PATH = Path(".alert_state/prod_health_alert_state.json")
DEFAULT_ALERT_COOLDOWN_SECONDS = 3 * 60 * 60


@dataclass(frozen=True)
class AlertEvent:
    code: str
    summary: str
    details: str


@dataclass(frozen=True)
class HealthSnapshot:
    environment: str
    checked_at_utc: str
    release_sha: str
    convention_mode_active: bool
    app_ok: bool
    db_ok: bool
    recommendation_ok: bool
    recommendation_state: str
    events: list[AlertEvent]


def check_prod_health(environment: str) -> HealthSnapshot:
    checked_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    release_sha = "unknown"
    convention_mode_active = False
    app_ok = False
    db_ok = False
    recommendation_ok = False
    recommendation_state = "unknown"
    events: list[AlertEvent] = []

    try:
        api_payload, _ = fetch_json(build_url(environment, "/api"))
        if api_payload.get("message") != "Board Game Recommender API":
            events.append(
                AlertEvent(
                    code="app_unreachable",
                    summary="/api returned unexpected payload",
                    details=f"payload={json.dumps(api_payload, sort_keys=True)}",
                )
            )
        else:
            app_ok = True
    except Exception as exc:
        events.append(
            AlertEvent(
                code="app_unreachable",
                summary="/api request failed",
                details=str(exc),
            )
        )

    try:
        version_payload, _ = fetch_json(build_url(environment, "/api/version"))
        release_sha = str(version_payload.get("git_sha", "unknown"))
        convention_mode_active = bool(version_payload.get("convention_mode", False))
    except Exception as exc:
        events.append(
            AlertEvent(
                code="app_unreachable",
                summary="/api/version request failed",
                details=str(exc),
            )
        )

    try:
        # Exercises database-backed query path.
        _, _ = fetch_json(
            build_url(
                environment,
                "/api/games/",
                query={"limit": 1, "skip": 0, "sort_by": "rank", "pax_only": "true"},
            )
        )
        db_ok = True
    except Exception as exc:
        events.append(
            AlertEvent(
                code="db_connectivity_failure",
                summary="/api/games query failed",
                details=str(exc),
            )
        )

    try:
        rec_status_payload, _ = fetch_json(
            build_url(environment, "/api/recommendations/status")
        )
        recommendation_state = str(rec_status_payload.get("state", "unknown"))
        recommendation_ok = bool(rec_status_payload.get("available", False))
        if not recommendation_ok:
            events.append(
                AlertEvent(
                    code="recommendation_degraded",
                    summary="Recommendation subsystem reported degraded mode",
                    details=json.dumps(rec_status_payload, sort_keys=True),
                )
            )
    except Exception as exc:
        events.append(
            AlertEvent(
                code="recommendation_degraded",
                summary="Recommendation status endpoint failed",
                details=str(exc),
            )
        )

    return HealthSnapshot(
        environment=environment,
        checked_at_utc=checked_at_utc,
        release_sha=release_sha,
        convention_mode_active=convention_mode_active,
        app_ok=app_ok,
        db_ok=db_ok,
        recommendation_ok=recommendation_ok,
        recommendation_state=recommendation_state,
        events=events,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run production P0 health checks and fail when unhealthy so GitHub workflow notifications fire."
        )
    )
    parser.add_argument(
        "--env",
        choices=["prod"],
        default="prod",
        help="Target environment (prod only for alerting workflow).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log alert details and exit with the same status behavior as runtime checks.",
    )
    parser.add_argument(
        "--state-path",
        default=str(DEFAULT_ALERT_STATE_PATH),
        help="Path for persisted alert state used for dedupe/transition detection.",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=int,
        default=DEFAULT_ALERT_COOLDOWN_SECONDS,
        help="Minimum time between repeated alerts for the same event code.",
    )
    return parser.parse_args()


def _parse_iso_timestamp(raw_value: str | None) -> datetime | None:
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value)
    except ValueError:
        return None


def load_alert_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load alert state from %s: %s", path, exc)
        return {}


def save_alert_state(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(path)
    except Exception as exc:
        logger.warning("Failed to persist alert state to %s: %s", path, exc)


def filter_alert_events(
    *,
    snapshot: HealthSnapshot,
    previous_state: dict,
    now_utc: datetime,
    cooldown_seconds: int,
) -> list[AlertEvent]:
    deduped_by_code: dict[str, AlertEvent] = {}
    for event in snapshot.events:
        deduped_by_code[event.code] = event

    output: list[AlertEvent] = []
    previous_recommendation_state = str(
        previous_state.get("last_recommendation_state", "unknown")
    )
    emitted_by_code = previous_state.get("last_emitted_at_utc_by_code", {})

    for code, event in deduped_by_code.items():
        if code == "recommendation_degraded":
            transitioned = (
                previous_recommendation_state in {"ready", "healthy"}
                and not snapshot.recommendation_ok
            )
            first_seen_degraded = (
                previous_recommendation_state == "unknown"
                and not snapshot.recommendation_ok
            )
            if not (transitioned or first_seen_degraded):
                continue

        last_emitted_raw = emitted_by_code.get(code)
        last_emitted_at = _parse_iso_timestamp(last_emitted_raw)
        if last_emitted_at is not None:
            elapsed_seconds = (now_utc - last_emitted_at).total_seconds()
            if elapsed_seconds < cooldown_seconds:
                continue

        output.append(event)
    return output


def main() -> int:
    args = parse_args()
    snapshot = check_prod_health(args.env)
    state_path = Path(args.state_path)
    previous_state = load_alert_state(state_path)
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)

    logger.info(
        "Health snapshot env=%s sha=%s convention_mode=%s app_ok=%s db_ok=%s rec_ok=%s rec_state=%s",
        snapshot.environment,
        snapshot.release_sha,
        snapshot.convention_mode_active,
        snapshot.app_ok,
        snapshot.db_ok,
        snapshot.recommendation_ok,
        snapshot.recommendation_state,
    )

    if not snapshot.convention_mode_active:
        logger.info("Convention mode is not active; skipping alert checks.")
        return 0

    filtered_events = filter_alert_events(
        snapshot=snapshot,
        previous_state=previous_state,
        now_utc=now_utc,
        cooldown_seconds=max(args.cooldown_seconds, 0),
    )

    if not filtered_events:
        # Always update recommendation state so transition detection is meaningful later.
        next_state = {
            "last_recommendation_state": snapshot.recommendation_state,
            "last_checked_at_utc": now_utc.isoformat(),
            "last_emitted_at_utc_by_code": previous_state.get(
                "last_emitted_at_utc_by_code", {}
            ),
        }
        save_alert_state(state_path, next_state)
        logger.info("No P0 alert conditions detected.")
        return 0

    logger.error("Detected %d P0 alert condition(s).", len(filtered_events))
    for event in filtered_events:
        logger.error("%s: %s (%s)", event.code, event.summary, event.details)

    emitted_map = dict(previous_state.get("last_emitted_at_utc_by_code", {}))
    for event in filtered_events:
        emitted_map[event.code] = now_utc.isoformat()
    next_state = {
        "last_recommendation_state": snapshot.recommendation_state,
        "last_checked_at_utc": now_utc.isoformat(),
        "last_emitted_at_utc_by_code": emitted_map,
    }
    save_alert_state(state_path, next_state)

    if args.dry_run:
        logger.info("Dry run enabled; alert details logged above.")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
