import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(app_storage_mode="local", app_data_dir=tmp_path)
    with TestClient(create_app(settings)) as test_client:
        yield test_client
