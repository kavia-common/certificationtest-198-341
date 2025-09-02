import asyncio

import pytest

from src.api.models import (
    CertificationStage,
    Domain,
    GitInfo,
    NotificationConfig,
    StageStatus,
    WorkflowCreateRequest,
    WorkflowUpdateStatusRequest,
)
from src.api.repository import compute_overall_status


def build_create_request(
    *,
    domain: Domain = Domain.CORE,
    author: str | None = "alice",
    stages: list[CertificationStage] | None = None,
    notify_on_start: bool = True,
    notify_on_finish: bool = True,
):
    git = GitInfo(
        repository="git@example.com:org/repo.git",
        folder="scripts/app",
        branch="main",
        commit_sha="c1",
        author=author,
    )
    notification = NotificationConfig(on_start=notify_on_start, on_finish=notify_on_finish)
    return WorkflowCreateRequest(
        git=git,
        domain=domain,
        stages=stages,
        metadata={"script_path": "scripts/app"},
        notification=notification,
        correlate_run_id="run-1",
    )


@pytest.mark.anyio
async def test_create_workflow_initializes_and_triggers(service, notifier):
    req = build_create_request()
    wf = await service.create_workflow(req)
    # Created, persisted
    assert wf.id
    stored = service.get_workflow(wf.id)
    assert stored is not None
    assert stored.status.name in ("CREATED", "QUEUED")  # kickoff will soon update to QUEUED
    # on_start notification recorded
    # The notification is async; give the event loop a chance
    await asyncio.sleep(0)
    assert any("created for" in msg for msg in notifier.messages)


@pytest.mark.anyio
async def test_kickoff_advances_stages_to_succeeded(service):
    req = build_create_request()
    wf = await service.create_workflow(req)
    # Wait enough for kickoff to sequentially finish stages
    await asyncio.sleep(0.25)
    final = service.get_workflow(wf.id)
    assert final is not None
    assert final.status.name == "SUCCEEDED"
    # All stages should be succeeded and have executor refs and durations
    for sr in final.stage_results.values():
        assert sr.status == StageStatus.SUCCEEDED
        assert sr.executor_ref is not None
        assert sr.duration_ms is not None and sr.duration_ms >= 0


@pytest.mark.anyio
async def test_update_stage_status_flow(service):
    req = build_create_request(stages=[CertificationStage.CODE_QUALITY])
    wf = await service.create_workflow(req)
    # Allow kickoff to set QUEUED and maybe move to running quickly
    await asyncio.sleep(0.05)
    # Explicitly update via callback-like behavior
    upd = WorkflowUpdateStatusRequest(stage=CertificationStage.CODE_QUALITY, status=StageStatus.RUNNING)
    service.update_stage_status(wf.id, upd)

    upd2 = WorkflowUpdateStatusRequest(stage=CertificationStage.CODE_QUALITY, status=StageStatus.SUCCEEDED, metrics={"score": 0.95})
    service.update_stage_status(wf.id, upd2)

    latest = service.get_workflow(wf.id)
    assert latest is not None
    sr = latest.stage_results[CertificationStage.CODE_QUALITY.value]
    assert sr.status == StageStatus.SUCCEEDED
    assert latest.status == compute_overall_status(latest.stage_results)
    assert sr.metrics == {"score": 0.95}


@pytest.mark.anyio
async def test_error_handling_when_execution_client_raises(monkeypatch, service):
    # Make trigger_stage raise for the first stage
    async def boom(*args, **kwargs):
        await asyncio.sleep(0)
        raise RuntimeError("boom")

    monkeypatch.setattr(service.exec_client, "trigger_stage", boom)
    req = build_create_request(stages=[CertificationStage.CODE_QUALITY])
    wf = await service.create_workflow(req)
    # Wait to allow failure path to complete
    await asyncio.sleep(0.15)
    latest = service.get_workflow(wf.id)
    assert latest is not None
    assert latest.status.name == "FAILED"
    sr = latest.stage_results[CertificationStage.CODE_QUALITY.value]
    assert sr.status == StageStatus.FAILED
    assert "boom" in (sr.error_message or "")
