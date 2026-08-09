from __future__ import annotations

import pytest

from mipserver.config import Cache, Settings


def test_cache_freshness_defaults_to_30_minutes() -> None:
    # model default; config.local.yaml may legitimately override the singleton, so only the
    # model default is asserted here
    assert Cache().freshness_minutes == 30.0


def test_cache_freshness_can_be_overridden_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CACHE__FRESHNESS_MINUTES", "0.25")

    fresh = Settings()  # type: ignore[call-arg]

    assert fresh.cache.freshness_minutes == 0.25


def test_env_overrides_yaml_for_keys_present_in_both(monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: YAML uses UPPERCASE aliases, env resolves to field names. Without the
    # alias-normalizing yaml source both land under different keys and YAML silently wins.
    monkeypatch.setenv("UVICORN__PORT", "9999")

    fresh = Settings()  # type: ignore[call-arg]

    assert fresh.uvicorn.port == 9999
    # sibling keys not touched by env must survive the merge
    assert fresh.uvicorn.app == "mipserver.app:app"
    # aliased-but-differently-named field must still resolve (GOTIFY -> gotifylist)
    assert len(fresh.gotifylist.root) > 0


def test_cache_freshness_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        Cache(freshness_minutes=-1)

    # validate_assignment=True -> the CLI override path in main.py is validated too
    with pytest.raises(ValueError):
        Cache().freshness_minutes = -1
