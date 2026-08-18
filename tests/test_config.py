# tests/test_config.py
from __future__ import annotations

import pytest

from toolchain.config import SITES, VALID_OUTPUTS, resolve_config
from toolchain.models import UserInputError


def test_defaults_to_cybertoolchain_site():
    config = resolve_config()
    assert config.site_key == "cybertoolchain"
    assert config.site is SITES["cybertoolchain"]
    assert config.site.api_base is not None


def test_aitoolchain_has_no_api_base_yet():
    config = resolve_config(site="aitoolchain")
    assert config.site.api_base is None
    assert config.site.site_base == "https://aitoolchain.io"


def test_unknown_site_raises_user_input_error():
    with pytest.raises(UserInputError, match="cybertoolchain, aitoolchain"):
        resolve_config(site="not-a-real-site")


def test_output_defaults_to_json():
    assert resolve_config().output == "json"


def test_invalid_output_raises_user_input_error():
    with pytest.raises(UserInputError):
        resolve_config(output="yaml")


def test_flag_beats_env(monkeypatch):
    monkeypatch.setenv("TOOLCHAIN_API_KEY", "ctk_from_env")
    config = resolve_config(api_key="ctk_from_flag")
    assert config.api_key == "ctk_from_flag"


def test_env_beats_default(monkeypatch):
    monkeypatch.setenv("TOOLCHAIN_SITE", "aitoolchain")
    config = resolve_config()
    assert config.site_key == "aitoolchain"


def test_timeout_defaults_to_30():
    assert resolve_config().timeout == 30.0


def test_valid_outputs_are_stable():
    assert VALID_OUTPUTS == ("json", "table", "csv", "tsv")
