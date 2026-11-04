#!/usr/bin/env python3

"""Report Fly Machines that are not stopped.

The script intentionally performs read-only inventory calls. It exits non-zero
when a machine is in a state that can consume compute, so GitHub Actions
workflow-failure notifications can deliver the alert.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from typing import Any, Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "https://api.machines.dev"
DEFAULT_PAGE_SIZE = 1000
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
IGNORED_MACHINE_STATES = frozenset({"stopped", "destroyed"})


class FlyApiError(RuntimeError):
    """Raised when the Fly Machines API cannot provide valid JSON."""


@dataclass(frozen=True)
class MachineObservation:
    app_name: str
    machine_id: str
    name: str
    state: str
    region: str
    updated_at: str

    @classmethod
    def from_api(cls, app_name: str, payload: dict[str, Any]) -> "MachineObservation":
        raw_state = str(payload.get("state", "")).strip().lower()
        return cls(
            app_name=app_name,
            machine_id=str(payload.get("id", "unknown")),
            name=str(payload.get("name", "unknown")),
            state=raw_state or "missing",
            region=str(payload.get("region", "unknown")),
            updated_at=str(payload.get("updated_at", "unknown")),
        )


def find_alert_machines(
    machines: Iterator[MachineObservation],
) -> list[MachineObservation]:
    """Return machines that are not stopped or already destroyed."""

    return sorted(
        (
            machine
            for machine in machines
            if machine.state not in IGNORED_MACHINE_STATES
        ),
        key=lambda machine: (machine.app_name, machine.machine_id),
    )


class FlyApiClient:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._opener = opener

    def _get_json(self, path: str, query: dict[str, str]) -> Any:
        query_string = urlencode(query)
        url = f"{self._base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with self._opener(
                request,
                timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
            ) as response:
                response_body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise FlyApiError(
                f"Fly API request failed with HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise FlyApiError(f"Fly API request failed: {exc.reason}") from exc
        except OSError as exc:
            raise FlyApiError(f"Fly API request failed: {exc}") from exc

        try:
            return json.loads(response_body)
        except (TypeError, json.JSONDecodeError) as exc:
            raise FlyApiError(f"Fly API returned invalid JSON for {path}") from exc

    def _list_pages(
        self,
        path: str,
        *,
        item_key: str,
        query: dict[str, str],
    ) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            page_query = {**query, "limit": str(DEFAULT_PAGE_SIZE)}
            if cursor:
                page_query["cursor"] = cursor
            payload = self._get_json(path, page_query)

            if isinstance(payload, list):
                # Older API responses returned an unwrapped list. Keep this
                # fallback because the endpoint still accepts non-paginated
                # clients and the monitor does not need to know the difference.
                items = payload
                next_cursor = None
            elif isinstance(payload, dict):
                items = payload.get(item_key)
                next_cursor = payload.get("next_cursor")
                if not isinstance(items, list):
                    raise FlyApiError(
                        f"Fly API response for {path} has no {item_key} list"
                    )
                if next_cursor is not None and not isinstance(next_cursor, str):
                    raise FlyApiError(
                        f"Fly API response for {path} has an invalid next_cursor"
                    )
            else:
                raise FlyApiError(f"Fly API response for {path} is not an object")

            for item in items:
                if not isinstance(item, dict):
                    raise FlyApiError(
                        f"Fly API response for {path} has an invalid item"
                    )
                yield item

            if not next_cursor:
                return
            if next_cursor == cursor:
                raise FlyApiError(f"Fly API returned a repeated cursor for {path}")
            cursor = next_cursor

    def list_apps(self, org_slug: str) -> list[dict[str, Any]]:
        return list(
            self._list_pages(
                "/v1/apps",
                item_key="apps",
                query={"org_slug": org_slug},
            )
        )

    def list_machines(self, app_name: str) -> list[dict[str, Any]]:
        path = f"/v1/apps/{quote(app_name, safe='')}/machines"
        return list(self._list_pages(path, item_key="machines", query={}))

    def inventory(self, org_slug: str) -> list[MachineObservation]:
        observations: list[MachineObservation] = []
        for app in self.list_apps(org_slug):
            app_name = str(app.get("name", "")).strip()
            if not app_name:
                raise FlyApiError("Fly API returned an app without a name")
            observations.extend(
                MachineObservation.from_api(app_name, machine)
                for machine in self.list_machines(app_name)
            )
        return observations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Alert when any Fly Machine in an organization is not stopped."
    )
    parser.add_argument(
        "--org-slug",
        default=os.getenv("FLY_ORG_SLUG", "").strip(),
        help="Fly organization slug (defaults to FLY_ORG_SLUG).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    org_slug = args.org_slug.strip()
    token = os.getenv("FLY_API_TOKEN", "").strip()
    if not org_slug:
        raise SystemExit("FLY_ORG_SLUG or --org-slug is required")
    if not token:
        raise SystemExit("FLY_API_TOKEN is required")

    try:
        machines = FlyApiClient(token).inventory(org_slug)
    except FlyApiError as exc:
        print(f"ERROR: unable to verify Fly Machine states: {exc}")
        return 2

    alert_machines = find_alert_machines(iter(machines))
    if not alert_machines:
        print(
            f"OK: all {len(machines)} Fly Machines in organization "
            f"{org_slug!r} are stopped or destroyed."
        )
        return 0

    print(
        f"ALERT: {len(alert_machines)} Fly Machine(s) in organization "
        f"{org_slug!r} are not stopped."
    )
    for machine in alert_machines:
        print(
            f"- app={machine.app_name} id={machine.machine_id} "
            f"name={machine.name} state={machine.state} "
            f"region={machine.region} updated_at={machine.updated_at}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
