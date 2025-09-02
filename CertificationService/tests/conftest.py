import asyncio
from typing import Generator

import pytest

from src.api.repository import InMemoryWorkflowRepository
from src.api.service import CertificationWorkflowService, ExecutionServiceClient, NotificationClient


@pytest.fixture(scope="session")
def anyio_backend():
    # Ensure pytest-anyio uses asyncio
    return "asyncio"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Session-scoped event loop for async tests.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class DummyExecClient(ExecutionServiceClient):
    """
    Dummy execution client that returns deterministic executor refs fast.
    """
    def __init__(self):
        super().__init__(base_url="http://dummy", timeout=0.01)

    async def trigger_stage(self, workflow_id, stage, git, metadata) -> str:  # type: ignore[override]
        await asyncio.sleep(0)  # yield control
        return f"exec-{workflow_id[:8]}-{stage.value}"


class DummyNotifier(NotificationClient):
    """
    Dummy notifier that records messages for assertions.
    """
    def __init__(self):
        self.messages = []

    async def notify(self, config, message: str) -> None:  # type: ignore[override]
        if config:
            self.messages.append(message)
        await asyncio.sleep(0)


@pytest.fixture()
def repo() -> InMemoryWorkflowRepository:
    return InMemoryWorkflowRepository()


@pytest.fixture()
def exec_client() -> DummyExecClient:
    return DummyExecClient()


@pytest.fixture()
def notifier() -> DummyNotifier:
    return DummyNotifier()


@pytest.fixture()
def service(repo, exec_client, notifier) -> CertificationWorkflowService:
    return CertificationWorkflowService(repo=repo, exec_client=exec_client, notifier=notifier)
