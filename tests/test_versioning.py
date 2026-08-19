# tests/test_versioning.py
from __future__ import annotations

from importlib import metadata

import httpx
import pytest

from toolchain import versioning


def test_current_version_reads_installed_package_metadata(monkeypatch):
    monkeypatch.setattr(metadata, "version", lambda name: "1.2.3")
    assert versioning.current_version() == "1.2.3"


def test_current_version_falls_back_when_package_not_found(monkeypatch):
    def raise_not_found(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", raise_not_found)
    assert versioning.current_version() == "0.0.0+unknown"


def test_latest_version_strips_a_leading_v(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"tag_name": "v2.5.0"}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    assert versioning.latest_version() == "2.5.0"


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("no route"), httpx.TimeoutException("slow")],
)
def test_latest_version_returns_none_on_network_failure(monkeypatch, failure):
    def raise_it(*a, **k):
        raise failure

    monkeypatch.setattr(httpx, "get", raise_it)
    assert versioning.latest_version() is None


def test_latest_version_returns_none_when_no_release_exists(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            raise httpx.HTTPStatusError("404", request=None, response=self)

        def json(self):
            return {}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse())
    assert versioning.latest_version() is None


def test_update_available_is_none_when_already_current(monkeypatch):
    monkeypatch.setattr(versioning, "latest_version", lambda **k: "1.0.0")
    monkeypatch.setattr(versioning, "current_version", lambda: "1.0.0")
    assert versioning.update_available() is None


def test_update_available_is_none_when_installed_is_newer(monkeypatch):
    # Shouldn't happen in practice (installed ahead of the latest tagged
    # release — e.g. an unreleased dev checkout) but must never report a
    # "downgrade" as an available update.
    monkeypatch.setattr(versioning, "latest_version", lambda **k: "1.0.0")
    monkeypatch.setattr(versioning, "current_version", lambda: "2.0.0")
    assert versioning.update_available() is None


def test_update_available_returns_the_newer_version(monkeypatch):
    monkeypatch.setattr(versioning, "latest_version", lambda **k: "2.0.0")
    monkeypatch.setattr(versioning, "current_version", lambda: "1.0.0")
    assert versioning.update_available() == "2.0.0"


def test_update_available_is_none_when_check_fails(monkeypatch):
    monkeypatch.setattr(versioning, "latest_version", lambda **k: None)
    assert versioning.update_available() is None
