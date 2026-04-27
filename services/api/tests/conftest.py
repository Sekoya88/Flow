import os

import pytest


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ.get("FLOW_DATABASE_URL", "postgresql://flow:flow@localhost:55432/flow")
