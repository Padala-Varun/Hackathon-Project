"""Shared fixtures: a full knowledge base built from the synthetic dataset in a temp folder, using the offline
hash embedder + numpy store (no model downloads, runs in seconds)."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import init_services
from scripts.make_synthetic import build


@pytest.fixture(scope="session")
def test_settings(tmp_path_factory) -> Settings:
    root = tmp_path_factory.mktemp("lni")
    build(root / "raw")
    return Settings(data_dir=root / "raw", store_dir=root / "store", embed_backend="hash", vector_backend="numpy",
                    use_reranker=False, llm_enabled=False, field_map=Path(__file__).resolve().parents[1] / "field_map.yaml")


@pytest.fixture(scope="session")
def services(test_settings):
    return init_services(test_settings)


@pytest.fixture(scope="session")
def kb(services):
    return services[0]


@pytest.fixture(scope="session")
def agent(services):
    return services[1]


@pytest.fixture(scope="session")
def client(services) -> TestClient:
    from app.main import app

    return TestClient(app)  # no lifespan: services are already initialised by the fixture
