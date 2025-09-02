from __future__ import annotations

import threading
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    CertificationStage,
    Domain,
    StageResult,
    StageStatus,
    Workflow,
    WorkflowStatus,
)

# Note: This is an in-memory repository for demonstration/testing.
# In production, replace with PostgreSQL-backed repository using env vars provided
# by the CertificationService_database component.


class InMemoryWorkflowRepository:
    """Thread-safe in-memory repository for Workflows."""

    def __init__(self) -> None:
        self._by_id: Dict[str, Workflow] = {}
        self._lock = threading.RLock()

    def _now(self) -> datetime:
        return datetime.utcnow()

    # PUBLIC_INTERFACE
    def create(self, wf: Workflow) -> Workflow:
        """Create and store a new workflow."""
        with self._lock:
            self._by_id[wf.id] = wf
        return wf

    # PUBLIC_INTERFACE
    def get(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by id."""
        with self._lock:
            return self._by_id.get(workflow_id)

    # PUBLIC_INTERFACE
    def update(self, wf: Workflow) -> Workflow:
        """Update existing workflow."""
        with self._lock:
            self._by_id[wf.id] = wf
        return wf

    # PUBLIC_INTERFACE
    def list(
        self,
        *,
        script_path: Optional[str] = None,
        domain: Optional[Domain] = None,
        author: Optional[str] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
        stage: Optional[CertificationStage] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Workflow]:
        """List workflows filtered by provided criteria."""
        with self._lock:
            values = list(self._by_id.values())

        def match(w: Workflow) -> bool:
            if domain and w.domain != domain:
                return False
            if author and (w.git.author or "").lower() != author.lower():
                return False
            if branch and w.git.branch != branch:
                return False
            if commit and w.git.commit_sha != commit:
                return False
            if status and w.status.value != status:
                return False
            if script_path:
                # Only match exact script_path in metadata
                meta_script = w.metadata.get("script_path") if w.metadata else None
                if meta_script != script_path:
                    return False
            if stage:
                if stage.value not in w.stage_results:
                    return False
            return True

        filtered = [w for w in values if match(w)]
        return filtered[offset : offset + limit]


# Helpers

DEFAULT_STAGES_BY_DOMAIN: Dict[Domain, List[CertificationStage]] = {
    Domain.CORE: [
        CertificationStage.CODE_QUALITY,
        CertificationStage.SECURITY,
        CertificationStage.FUNCTIONAL,
    ],
    Domain.TRANSPORT: [
        CertificationStage.CODE_QUALITY,
        CertificationStage.SECURITY,
        CertificationStage.FUNCTIONAL,
        CertificationStage.PERFORMANCE,
    ],
    Domain.BANKING: [
        CertificationStage.CODE_QUALITY,
        CertificationStage.SECURITY,
        CertificationStage.COMPLIANCE,
        CertificationStage.FUNCTIONAL,
        CertificationStage.E2E,
    ],
    Domain.HEALTHCARE: [
        CertificationStage.CODE_QUALITY,
        CertificationStage.SECURITY,
        CertificationStage.COMPLIANCE,
        CertificationStage.FUNCTIONAL,
        CertificationStage.SOAK,
    ],
}


def new_workflow_id() -> str:
    return str(uuid.uuid4())


def init_stage_results(stages: List[CertificationStage]) -> Dict[str, StageResult]:
    return {
        s.value: StageResult(stage=s, status=StageStatus.PENDING, started_at=None, finished_at=None)
        for s in stages
    }


def compute_overall_status(results: Dict[str, StageResult]) -> WorkflowStatus:
    any_failed = any(r.status == StageStatus.FAILED for r in results.values())
    any_running = any(r.status == StageStatus.RUNNING for r in results.values())
    all_succeeded = all(r.status == StageStatus.SUCCEEDED for r in results.values())
    any_started = any(r.status in (StageStatus.RUNNING, StageStatus.SUCCEEDED, StageStatus.FAILED, StageStatus.SKIPPED) for r in results.values())

    if any_failed:
        return WorkflowStatus.FAILED
    if all_succeeded and len(results) > 0:
        return WorkflowStatus.SUCCEEDED
    if any_running:
        return WorkflowStatus.RUNNING
    if any_started:
        return WorkflowStatus.PARTIAL
    return WorkflowStatus.CREATED
