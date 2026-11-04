from __future__ import annotations

import json

import pytest

from scripts.alerts.check_fly_machines import (
    FlyApiClient,
    FlyApiError,
    MachineObservation,
    find_alert_machines,
)


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_find_alert_machines_ignores_stopped_and_destroyed() -> None:
    machines = iter(
        [
            MachineObservation("prod", "2", "started", "started", "iad", ""),
            MachineObservation("prod", "1", "stopped", "stopped", "iad", ""),
            MachineObservation("prod", "3", "destroyed", "destroyed", "iad", ""),
        ]
    )

    alert_machines = find_alert_machines(machines)

    assert [machine.machine_id for machine in alert_machines] == ["2"]


def test_inventory_reads_apps_and_machines_with_pagination() -> None:
    responses = iter(
        [
            {"apps": [{"name": "app-a"}], "next_cursor": "next-apps"},
            {"apps": [{"name": "app-b"}]},
            {"machines": [{"id": "machine-a", "state": "stopped"}]},
            {"machines": [{"id": "machine-b", "state": "started"}]},
        ]
    )

    def fake_opener(request: object, *, timeout: int) -> _FakeResponse:
        del request, timeout
        return _FakeResponse(next(responses))

    machines = FlyApiClient("token", opener=fake_opener).inventory("personal")

    assert [(machine.app_name, machine.state) for machine in machines] == [
        ("app-a", "stopped"),
        ("app-b", "started"),
    ]


def test_inventory_rejects_malformed_list_response() -> None:
    def fake_opener(request: object, *, timeout: int) -> _FakeResponse:
        del request, timeout
        return _FakeResponse({"unexpected": []})

    with pytest.raises(FlyApiError, match="has no apps list"):
        FlyApiClient("token", opener=fake_opener).inventory("personal")
