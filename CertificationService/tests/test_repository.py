from datetime import datetime, timedelta

from src.api.models import (
    CertificationStage,
    Domain,
    GitInfo,
    StageResult,
    StageStatus,
    Workflow,
    WorkflowStatus,
)
from src.api.repository import (
    InMemoryWorkflowRepository,
    compute_overall_status,
    init_stage_results,
)


def build_workflow(
    *,
    id_: str = "wf-1",
    domain: Domain = Domain.CORE,
    author: str | None = "alice",
    branch: str = "main",
    commit: str = "abc123",
    stages: list[CertificationStage] | None = None,
    metadata: dict[str, str] | None = None,
) -> Workflow:
    stages = stages or [CertificationStage.CODE_QUALITY, CertificationStage.SECURITY]
    git = GitInfo(repository="git@example.com:org/repo.git", folder="scripts/app", branch=branch, commit_sha=commit, author=author)
    now = datetime.utcnow()
    return Workflow(
        id=id_,
        correlate_run_id=None,
        git=git,
        domain=domain,
        stages=stages,
        status=WorkflowStatus.CREATED,
        created_at=now,
        updated_at=now,
        stage_results=init_stage_results(stages),
        metadata=metadata or {},
        notification=None,
    )


def test_init_stage_results_sets_pending_for_all():
    stages = [CertificationStage.CODE_QUALITY, CertificationStage.SECURITY]
    results = init_stage_results(stages)
    assert set(results.keys()) == {s.value for s in stages}
    for r in results.values():
        assert r.status == StageStatus.PENDING
        assert r.started_at is None
        assert r.finished_at is None


def test_compute_overall_status_transitions():
    stages = [CertificationStage.CODE_QUALITY, CertificationStage.SECURITY]
    results = init_stage_results(stages)
    # Initially created
    assert compute_overall_status(results) == WorkflowStatus.CREATED

    # One running => RUNNING
    results[CertificationStage.CODE_QUALITY.value].status = StageStatus.RUNNING
    assert compute_overall_status(results) == WorkflowStatus.RUNNING

    # One succeeded, one pending => PARTIAL
    results[CertificationStage.CODE_QUALITY.value].status = StageStatus.SUCCEEDED
    assert compute_overall_status(results) == WorkflowStatus.PARTIAL

    # All succeeded => SUCCEEDED
    results[CertificationStage.SECURITY.value].status = StageStatus.SUCCEEDED
    assert compute_overall_status(results) == WorkflowStatus.SUCCEEDED

    # Any failed => FAILED
    results[CertificationStage.SECURITY.value].status = StageStatus.FAILED
    assert compute_overall_status(results) == WorkflowStatus.FAILED


def test_repository_filters_by_fields():
    repo = InMemoryWorkflowRepository()
    wf1 = build_workflow(id_="wf1", domain=Domain.CORE, author="alice", branch="main", commit="c1", metadata={"script_path": "scripts/app"})
    wf2 = build_workflow(id_="wf2", domain=Domain.TRANSPORT, author="bob", branch="dev", commit="c2", metadata={"script_path": "scripts/other"})
    repo.create(wf1)
    repo.create(wf2)

    # domain filter
    res = repo.list(domain=Domain.CORE)
    assert [w.id for w in res] == ["wf1"]

    # author filter (case-insensitive)
    res = repo.list(author="ALICE")
    assert [w.id for w in res] == ["wf1"]

    # branch filter
    res = repo.list(branch="dev")
    assert [w.id for w in res] == ["wf2"]

    # commit filter
    res = repo.list(commit="c2")
    assert [w.id for w in res] == ["wf2"]

    # script_path by metadata
    res = repo.list(script_path="scripts/app")
    assert [w.id for w in res] == ["wf1"]

    # stage filter: initially pending stages exist, so stage key is present
    res = repo.list(stage=CertificationStage.SECURITY)
    assert set(w.id for w in res) == {"wf1", "wf2"}

    # status filter: adjust status to succeeded and then filter
    wf1.stage_results[CertificationStage.CODE_QUALITY.value].status = StageStatus.SUCCEEDED
    wf1.stage_results[CertificationStage.SECURITY.value].status = StageStatus.SUCCEEDED
    # recompute
    wf1.status = compute_overall_status(wf1.stage_results)
    repo.update(wf1)

    res = repo.list(status="succeeded")
    assert [w.id for w in res] == ["wf1"]


def test_duration_computation_consistency():
    # validate a typical duration computation behavior
    sr = StageResult(stage=CertificationStage.CODE_QUALITY, status=StageStatus.RUNNING)
    sr.started_at = datetime.utcnow() - timedelta(milliseconds=120)
    sr.finished_at = datetime.utcnow()
    # emulate service behavior:
    if sr.started_at:
        sr.duration_ms = int((sr.finished_at - sr.started_at).total_seconds() * 1000)
    assert sr.duration_ms is not None
    assert 100 <= sr.duration_ms <= 300  # allow some tolerance
