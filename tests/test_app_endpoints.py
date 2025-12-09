from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

import mipserver.app as appmod
from mipserver.Helper import MIPServerHelper


def test_root_returns_hello(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Hello World"}


def test_echo_without_param(client: TestClient) -> None:
    # Use a custom Host header and query to ensure fields are set
    r = client.get("/echo", headers={"Host": "example.test:9999", "X-Custom": "abc"})

    assert r.status_code == 200


def test_echo_includes_headers_and_url(client: TestClient) -> None:
    # Use a custom Host header and query to ensure fields are set
    r = client.get("/echo?x=1", headers={"Host": "example.test:9999", "X-Custom": "abc"})

    assert r.status_code == 200
    data = r.json()

    # basic structure
    assert "headers" in data and isinstance(data["headers"], dict)
    assert data["headers"].get("x-custom") == "abc"
    assert data["request_path"] == "/echo"
    assert data["request_url_full"].endswith("/echo?x=1")
    # url_components may be None for hostname/port depending on the test server, but scheme should exist
    assert data["url_components"]["scheme"] in {"http", "https"}


def test_package_json_invalid_package_returns_error(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure mapping does not contain the requested package
    def fake_get_package_name_to_repo() -> Dict[str, str]:
        return {}

    # Override the dependency in the FastAPI app
    from mipserver.app import app

    app.dependency_overrides[appmod.get_package_name_to_repo] = fake_get_package_name_to_repo

    try:
        r = client.get("/package/py/nonexistentpkg/latest.json")
        assert r.status_code == 500
        assert r.json()["error"].startswith("cannot generate package -> invalid packagename")
    finally:
        app.dependency_overrides.clear()


def test_package_json_uses_fresh_local_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Map package name and force local_json path to exist and be fresh

    def fake_get_package_name_to_repo() -> Dict[str, str]:
        return {"demo": "someone/repo"}

    # Override the dependency in the FastAPI app
    from mipserver.app import app

    app.dependency_overrides[appmod.get_package_name_to_repo] = fake_get_package_name_to_repo

    local_json = tmp_path / "py" / "demo" / "latest.json"
    local_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {"hashes": [["demo.mpy", "a" * 64]]}
    local_json.write_text(json.dumps(payload))

    # Point helper to our tmp_path for package json
    def fake_get_local_path_for_package_json_by_package_and_version(self: MIPServerHelper, mpy_version: Any, package_name: str, pversion: str) -> Path:  # type: ignore[override]
        return local_json

    monkeypatch.setattr(
        MIPServerHelper,
        "get_local_path_for_package_json_by_package_and_version",
        fake_get_local_path_for_package_json_by_package_and_version,
    )

    try:
        r = client.get("/package/py/demo/latest.json")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/json")
        assert r.json() == payload
    finally:
        app.dependency_overrides.clear()


def test_package_json_git_pull_failure(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_package_name_to_repo() -> Dict[str, str]:
        return {"demo": "someone/repo"}

    # Override the dependency in the FastAPI app
    from mipserver.app import app

    app.dependency_overrides[appmod.get_package_name_to_repo] = fake_get_package_name_to_repo

    # Ensure local json is missing so code proceeds to git pull
    def fake_get_local_path_for_package_json_by_package_and_version(self: MIPServerHelper, mpy_version: Any, package_name: str, pversion: str) -> Path:  # type: ignore[override]
        p = tmp_path / str(mpy_version) / package_name / f"{pversion}.json"
        return p

    def fake_ensure_git_repo_up_to_date(self: MIPServerHelper, repo_name: str, branch: str) -> Path | None:  # type: ignore[override]
        return None

    monkeypatch.setattr(
        MIPServerHelper,
        "get_local_path_for_package_json_by_package_and_version",
        fake_get_local_path_for_package_json_by_package_and_version,
    )
    monkeypatch.setattr(MIPServerHelper, "ensure_git_repo_up_to_date", fake_ensure_git_repo_up_to_date)

    try:
        r = client.get("/package/py/demo/latest.json")
        assert r.status_code == 500
        assert "git pull failed" in r.json()["error"]
    finally:
        app.dependency_overrides.clear()


def test_package_json_generate_success(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # monkeypatch.setattr(appmod, "PACKAGE_NAME_TO_REPO", {"demo": "someone/repo"}, raising=False)

    def fake_get_package_name_to_repo() -> Dict[str, str]:
        return {"demo": "someone/repo"}

    # Override the dependency in the FastAPI app
    from mipserver.app import app

    app.dependency_overrides[appmod.get_package_name_to_repo] = fake_get_package_name_to_repo

    def fake_get_local_path_for_package_json_by_package_and_version(self: MIPServerHelper, mpy_version: Any, package_name: str, pversion: str) -> Path:  # type: ignore[override]
        return tmp_path / str(mpy_version) / package_name / f"{pversion}.json"

    def fake_ensure_git_repo_up_to_date(self: MIPServerHelper, repo_name: str, branch: str) -> Path | None:  # type: ignore[override]
        p = tmp_path / "gitrepo"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def fake_generate_package_json_from_local_repo(self: MIPServerHelper, gitrepopath: Path, target_pkgjson: Path, mpy_version: Any) -> Path:  # type: ignore[override]
        target_pkgjson.parent.mkdir(parents=True, exist_ok=True)
        data = {"hashes": [["demo.mpy", "b" * 64]]}
        target_pkgjson.write_text(json.dumps(data))
        return target_pkgjson

    monkeypatch.setattr(
        MIPServerHelper,
        "get_local_path_for_package_json_by_package_and_version",
        fake_get_local_path_for_package_json_by_package_and_version,
    )
    monkeypatch.setattr(MIPServerHelper, "ensure_git_repo_up_to_date", fake_ensure_git_repo_up_to_date)
    monkeypatch.setattr(
        MIPServerHelper, "generate_package_json_from_local_repo", fake_generate_package_json_from_local_repo
    )

    try:
        r = client.get("/package/6/demo/latest.json")
        assert r.status_code == 200
        body = r.json()
        assert body["hashes"][0][0] == "demo.mpy"
        assert body["hashes"][0][1] == "b" * 64
    finally:
        # Clean up the override
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "short2,short64,status",
    [
        ("ab", "c" * 63, 422),
        ("abc", "c" * 64, 422),
    ],
)
def test_file_param_validation(client: TestClient, short2: str, short64: str, status: int) -> None:
    r = client.get(f"/file/{short2}/{short64}")
    assert r.status_code == status


def test_file_not_found_returns_error(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure helper maps to tmp_path but file does not exist
    target_rel = "files/aa/" + "a" * 64

    def fake_get_local_path_for(self: MIPServerHelper, file_path: str | Path) -> Path:  # type: ignore[override]
        return tmp_path / Path(str(file_path))

    monkeypatch.setattr(MIPServerHelper, "get_local_path_for", fake_get_local_path_for)

    r = client.get(f"/file/aa/{'a'*64}")
    assert r.status_code == 500
    assert "File not found" in r.json()["error"] or "File error" in r.json()["error"]


def test_file_happy_path_returns_bytes(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = b"hello-bytes"
    short_hash = "a" * 64
    shard = short_hash[:2]
    the_file = tmp_path / "files" / shard / short_hash
    the_file.parent.mkdir(parents=True, exist_ok=True)
    the_file.write_bytes(content)

    def fake_get_local_path_for(self: MIPServerHelper, file_path: str | Path) -> Path:  # type: ignore[override]
        # map to our tmp structure
        return tmp_path / Path(str(file_path))

    monkeypatch.setattr(MIPServerHelper, "get_local_path_for", fake_get_local_path_for)

    r = client.get(f"/file/{shard}/{short_hash}")
    assert r.status_code == 200
    assert r.headers.get("content-type") == "application/octet-stream"
    assert r.content == content


def test_catch_all_unknown_returns_error(client: TestClient) -> None:
    r = client.get("/this/path/does/not/exist")
    assert r.status_code == 500
    assert r.json()["error"] == "UNKNOWN"
