#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os

try:
    from validation_common import (
        build_url,
        fetch_json,
        request_with_retry,
    )
except ModuleNotFoundError:
    from scripts.validation_common import (
        build_url,
        fetch_json,
        request_with_retry,
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


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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


def _render_alert_subject(snapshot: HealthSnapshot) -> str:
    codes = ", ".join(sorted({event.code for event in snapshot.events}))
    return f"[pax-tt][{snapshot.environment}] P0 alert: {codes}"


def _render_alert_html(snapshot: HealthSnapshot) -> str:
    rows = "".join(
        f"<li><strong>{event.code}</strong>: {event.summary}<br/><code>{event.details}</code></li>"
        for event in snapshot.events
    )
    return (
        "<h2>pax_tt_recommender production health alert</h2>"
        f"<p><strong>Environment:</strong> {snapshot.environment}</p>"
        f"<p><strong>Checked at:</strong> {snapshot.checked_at_utc}</p>"
        f"<p><strong>Release SHA:</strong> {snapshot.release_sha}</p>"
        f"<p><strong>App OK:</strong> {snapshot.app_ok}</p>"
        f"<p><strong>DB OK:</strong> {snapshot.db_ok}</p>"
        f"<p><strong>Recommendation OK:</strong> {snapshot.recommendation_ok}"
        f" ({snapshot.recommendation_state})</p>"
        f"<ul>{rows}</ul>"
    )


def _send_resend_email(*, api_key: str, from_email: str, to_emails: list[str], subject: str, html: str) -> None:
    payload = {
        "from": from_email,
        "to": to_emails,
        "subject": subject,
        "html": html,
    }
    request_with_retry(
        "https://api.resend.com/emails",
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
        timeout=20,
    )


def _send_sendgrid_email(*, api_key: str, from_email: str, to_emails: list[str], subject: str, html: str) -> None:
    payload = {
        "personalizations": [
            {
                "to": [{"email": email} for email in to_emails],
                "subject": subject,
            }
        ],
        "from": {"email": from_email},
        "content": [{"type": "text/html", "value": html}],
    }
    request_with_retry(
        "https://api.sendgrid.com/v3/mail/send",
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode("utf-8"),
        timeout=20,
    )


def send_alert_email(snapshot: HealthSnapshot) -> str:
    to_emails = _split_csv(os.getenv("ALERT_EMAIL_TO"))
    from_email = os.getenv("ALERT_EMAIL_FROM", "alerts@pax-tt-app.local")
    if not to_emails:
        logger.info("ALERT_EMAIL_TO not configured; skipping email send.")
        return "disabled"

    subject = _render_alert_subject(snapshot)
    html = _render_alert_html(snapshot)

    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "").strip()

    if resend_api_key:
        try:
            _send_resend_email(
                api_key=resend_api_key,
                from_email=from_email,
                to_emails=to_emails,
                subject=subject,
                html=html,
            )
            return "resend"
        except Exception as exc:
            logger.warning("Resend delivery failed, attempting SendGrid fallback: %s", exc)

    if sendgrid_api_key:
        _send_sendgrid_email(
            api_key=sendgrid_api_key,
            from_email=from_email,
            to_emails=to_emails,
            subject=subject,
            html=html,
        )
        return "sendgrid"

    logger.info(
        "No email provider configured; relying on workflow failure notifications."
    )
    return "disabled"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run production health checks and send P0 alert emails when unhealthy."
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
        help="Log alert payload and exit without sending email.",
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
        logger.info("Dry run enabled; skipping email send.")
        logger.info("Subject: %s", _render_alert_subject(snapshot))
        logger.info("Body: %s", _render_alert_html(snapshot))
        return 1

    provider = send_alert_email(snapshot)
    if provider == "disabled":
        logger.info("Alert email delivery is disabled for this run.")
    else:
        logger.info("Alert email sent via %s.", provider)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
