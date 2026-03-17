#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path

try:
    from validation_common import (
        build_url,
        fetch_json,
        measure_json_request,
    )
except ModuleNotFoundError:
    from scripts.validation_common import (
        build_url,
        fetch_json,
        measure_json_request,
    )

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)
DEFAULT_ALERT_STATE_PATH = Path(".alert_state/prod_health_alert_state.json")
DEFAULT_ALERT_COOLDOWN_SECONDS = 3 * 60 * 60
DEFAULT_SUSTAINED_LATENCY_CONSECUTIVE_BREACHES = 3
DEFAULT_CATALOG_LATENCY_THRESHOLD_MS = 1000.0
DEFAULT_RECOMMENDATION_LATENCY_THRESHOLD_MS = 2500.0
DEFAULT_ALERT_RECOMMENDATION_GAME_ID = 224517


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
    api_latency_ms: float | None
    api_version_latency_ms: float | None
    recommendations_latency_ms: float | None
    events: list[AlertEvent]


def _append_github_summary(lines: list[str]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if not summary_path:
        return
    try:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except Exception as exc:
        logger.warning("Failed to append GitHub summary: %s", exc)


def check_prod_health(environment: str) -> HealthSnapshot:
    checked_at_utc = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    release_sha = "unknown"
    convention_mode_active = False
    app_ok = False
    db_ok = False
    recommendation_ok = False
    recommendation_state = "unknown"
    api_latency_ms: float | None = None
    api_version_latency_ms: float | None = None
    recommendations_latency_ms: float | None = None
    events: list[AlertEvent] = []

    try:
        api_payload, api_latency_ms = measure_json_request(
            build_url(environment, "/api")
        )
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
        version_payload, api_version_latency_ms = measure_json_request(
            build_url(environment, "/api/version")
        )
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
                query={
                    "limit": 1,
                    "skip": 0,
                    "sort_by": "rank",
                    "library_only": "true",
                },
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

    recommendation_game_id = int(
        os.getenv("ALERT_RECOMMENDATION_GAME_ID", DEFAULT_ALERT_RECOMMENDATION_GAME_ID)
    )
    try:
        _, recommendations_latency_ms = measure_json_request(
            build_url(environment, f"/api/recommendations/{recommendation_game_id}")
        )
    except Exception as exc:
        logger.warning("Could not measure recommendation endpoint latency: %s", exc)

    threshold_catalog_ms = float(
        os.getenv(
            "ALERT_CATALOG_LATENCY_THRESHOLD_MS", DEFAULT_CATALOG_LATENCY_THRESHOLD_MS
        )
    )
    threshold_recommendation_ms = float(
        os.getenv(
            "ALERT_RECOMMENDATION_LATENCY_THRESHOLD_MS",
            DEFAULT_RECOMMENDATION_LATENCY_THRESHOLD_MS,
        )
    )
    breached_points: list[str] = []
    if api_latency_ms is not None and api_latency_ms > threshold_catalog_ms:
        breached_points.append(
            f"/api={api_latency_ms:.1f}ms>{threshold_catalog_ms:.1f}ms"
        )
    if (
        api_version_latency_ms is not None
        and api_version_latency_ms > threshold_catalog_ms
    ):
        breached_points.append(
            f"/api/version={api_version_latency_ms:.1f}ms>{threshold_catalog_ms:.1f}ms"
        )
    if (
        recommendations_latency_ms is not None
        and recommendations_latency_ms > threshold_recommendation_ms
    ):
        breached_points.append(
            "/api/recommendations/"
            f"{recommendation_game_id}={recommendations_latency_ms:.1f}ms>"
            f"{threshold_recommendation_ms:.1f}ms"
        )
    if breached_points:
        events.append(
            AlertEvent(
                code="latency_sustained_breach",
                summary="Latency thresholds exceeded",
                details="; ".join(breached_points),
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
        api_latency_ms=api_latency_ms,
        api_version_latency_ms=api_version_latency_ms,
        recommendations_latency_ms=recommendations_latency_ms,
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
) -> tuple[list[AlertEvent], int]:
    deduped_by_code: dict[str, AlertEvent] = {}
    for event in snapshot.events:
        deduped_by_code[event.code] = event

    output: list[AlertEvent] = []
    previous_recommendation_state = str(
        previous_state.get("last_recommendation_state", "unknown")
    )
    emitted_by_code = previous_state.get("last_emitted_at_utc_by_code", {})

    latency_streak = int(previous_state.get("latency_breach_streak", 0))
    has_latency_breach = "latency_sustained_breach" in deduped_by_code
    if has_latency_breach:
        latency_streak += 1
    else:
        latency_streak = 0

    required_latency_breaches = int(
        os.getenv(
            "ALERT_LATENCY_SUSTAINED_BREACHES",
            DEFAULT_SUSTAINED_LATENCY_CONSECUTIVE_BREACHES,
        )
    )

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
        if code == "latency_sustained_breach" and latency_streak < max(
            required_latency_breaches, 1
        ):
            continue

        last_emitted_raw = emitted_by_code.get(code)
        last_emitted_at = _parse_iso_timestamp(last_emitted_raw)
        if last_emitted_at is not None:
            elapsed_seconds = (now_utc - last_emitted_at).total_seconds()
            if elapsed_seconds < cooldown_seconds:
                continue

        output.append(event)
    return output, latency_streak


def main() -> int:
    args = parse_args()
    snapshot = check_prod_health(args.env)
    state_path = Path(args.state_path)
    previous_state = load_alert_state(state_path)
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)

    logger.info(
        "Health snapshot env=%s sha=%s convention_mode=%s app_ok=%s db_ok=%s rec_ok=%s rec_state=%s api_ms=%s api_version_ms=%s rec_ms=%s",
        snapshot.environment,
        snapshot.release_sha,
        snapshot.convention_mode_active,
        snapshot.app_ok,
        snapshot.db_ok,
        snapshot.recommendation_ok,
        snapshot.recommendation_state,
        f"{snapshot.api_latency_ms:.1f}"
        if snapshot.api_latency_ms is not None
        else "n/a",
        f"{snapshot.api_version_latency_ms:.1f}"
        if snapshot.api_version_latency_ms is not None
        else "n/a",
        f"{snapshot.recommendations_latency_ms:.1f}"
        if snapshot.recommendations_latency_ms is not None
        else "n/a",
    )

    if not snapshot.convention_mode_active:
        logger.info("Convention mode is not active; skipping alert checks.")
        return 0

    filtered_events, latency_streak = filter_alert_events(
        snapshot=snapshot,
        previous_state=previous_state,
        now_utc=now_utc,
        cooldown_seconds=max(args.cooldown_seconds, 0),
    )
    current_active_codes = {event.code for event in snapshot.events}
    sustained_latency_required = int(
        os.getenv(
            "ALERT_LATENCY_SUSTAINED_BREACHES",
            DEFAULT_SUSTAINED_LATENCY_CONSECUTIVE_BREACHES,
        )
    )
    if latency_streak < max(sustained_latency_required, 1):
        current_active_codes.discard("latency_sustained_breach")

    previous_active_codes = {
        str(code) for code in previous_state.get("active_alert_codes", [])
    }
    recovered_codes = sorted(previous_active_codes - current_active_codes)
    for code in recovered_codes:
        logger.info(
            "RECOVERY: %s recovered in %s (sha=%s).",
            code,
            snapshot.environment,
            snapshot.release_sha,
        )
        print(
            "::notice::Recovery detected for "
            f"{code} in {snapshot.environment} (sha={snapshot.release_sha})"
        )
    if recovered_codes:
        _append_github_summary(
            [
                "### Recovery Notifications",
                *[f"- {code} recovered" for code in recovered_codes],
            ]
        )

    if not filtered_events:
        # Always update recommendation state so transition detection is meaningful later.
        next_state = {
            "last_recommendation_state": snapshot.recommendation_state,
            "last_checked_at_utc": now_utc.isoformat(),
            "latency_breach_streak": latency_streak,
            "active_alert_codes": sorted(current_active_codes),
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
    _append_github_summary(
        [
            "### Active Alerts",
            *[f"- {event.code}: {event.summary}" for event in filtered_events],
        ]
    )
    next_state = {
        "last_recommendation_state": snapshot.recommendation_state,
        "last_checked_at_utc": now_utc.isoformat(),
        "latency_breach_streak": latency_streak,
        "active_alert_codes": sorted(current_active_codes),
        "last_emitted_at_utc_by_code": emitted_map,
    }
    save_alert_state(state_path, next_state)

    if args.dry_run:
        logger.info("Dry run enabled; alert details logged above.")
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
