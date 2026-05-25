from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.database import get_session_local
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
  monkeypatch.setenv("SEIZURE_SENSOR_DB_PATH", str(tmp_path / "test.sqlite"))
  with TestClient(app) as test_client:
    yield test_client


@pytest.fixture()
def db_session():
  db = get_session_local()()
  try:
    yield db
  finally:
    db.close()
