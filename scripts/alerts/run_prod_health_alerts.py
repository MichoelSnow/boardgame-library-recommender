#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging

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
        rec_status_payload, _ = fetch_json(build_url(environment, "/api/recommendations/status"))
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = check_prod_health(args.env)

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

    if not snapshot.events:
        logger.info("No P0 alert conditions detected.")
        return 0

    logger.error("Detected %d P0 alert condition(s).", len(snapshot.events))
    for event in snapshot.events:
        logger.error("%s: %s (%s)", event.code, event.summary, event.details)

    if args.dry_run:
        logger.info("Dry run enabled; alert details logged above.")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
