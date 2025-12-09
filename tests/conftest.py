import pytest
from fastapi.testclient import TestClient

from mipserver.app import app

print("Conftest... initializing fixture...")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
