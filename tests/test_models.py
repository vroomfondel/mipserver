from __future__ import annotations

import pytest

from mipserver.datastructures.models import (
    MIPServerFileL,
    MIPServerPackageJson,
    MIPSRCPackageJson,
    MIPSRCPackageURLEntry,
)


def test_fileL_serializes_as_two_element_array() -> None:
    entry = MIPServerFileL(path="demo.mpy", hash="a" * 64)

    assert entry.model_dump() == ["demo.mpy", "a" * 64]
    assert MIPServerPackageJson(hashes=[entry]).model_dump() == {"hashes": [["demo.mpy", "a" * 64]]}


def test_src_url_entry_accepts_upstream_array_form() -> None:
    entry = MIPSRCPackageURLEntry.model_validate(["target.py", "src.py"])

    assert entry.url_from == "target.py"
    assert entry.url_to == "src.py"


def test_src_url_entry_accepts_keyword_form() -> None:
    # regression: the before-validator used to return None for non-list input,
    # which made the ordinary constructor unusable
    entry = MIPSRCPackageURLEntry(url_from="target.py", url_to="src.py")

    assert (entry.url_from, entry.url_to) == ("target.py", "src.py")


def test_src_url_entry_rejects_wrong_arity() -> None:
    with pytest.raises(Exception):
        MIPSRCPackageURLEntry.model_validate(["only-one"])


def test_src_package_json_parses_upstream_shape() -> None:
    parsed = MIPSRCPackageJson(version="1.2.3", urls=[["a.py", "src/a.py"], ["b.py", "src/b.py"]])  # type: ignore[list-item]

    assert parsed.version == "1.2.3"
    assert [(u.url_from, u.url_to) for u in parsed.urls] == [("a.py", "src/a.py"), ("b.py", "src/b.py")]
