from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    CertificationStage,
    GitInfo,
    NotificationConfig,
    StageResult,
    StageStatus,
    Workflow,
    WorkflowStatus,
    WorkflowCreateRequest,
    WorkflowUpdateStatusRequest,
)
from .repository import (
    DEFAULT_STAGES_BY_DOMAIN,
    InMemoryWorkflowRepository,
    compute_overall_status,
    init_stage_results,
    new_workflow_id,
)


class ExecutionServiceClient:
    """HTTP client to communicate with ExecutionService.
    URLs are currently placeholders; replace with env configuration when available.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0) -> None:
        # NOTE: This should be configured using environment variables
        # e.g., EXECUTION_SERVICE_URL
        self.base_url = base_url or "http://execution-service:8000"
        self.timeout = timeout

    # PUBLIC_INTERFACE
    async def trigger_stage(
        self,
        workflow_id: str,
        stage: CertificationStage,
        git: GitInfo,
        metadata: Dict[str, str],
    ) -> str:
        """Trigger execution for a stage. Returns an executor reference id."""
        # Placeholder implementation; in real scenario, POST to ExecutionService.
        # Simulate async external call delay.
        await asyncio.sleep(0.05)
        # Return a mock executor ref
        return f"exec-{workflow_id[:8]}-{stage.value}"


class NotificationClient:
    """Notification client stub (webhook/email/slack)."""

    # PUBLIC_INTERFACE
    async def notify(self, config: Optional[NotificationConfig], message: str) -> None:
        """Send a notification based on provided configuration (stub)."""
        if not config:
            return
        # In a real implementation, send HTTP webhook, email, or Slack message.
        await asyncio.sleep(0.01)
        return


class CertificationWorkflowService:
    """Business logic for certification workflow orchestration."""

    def __init__(
        self,
        repo: InMemoryWorkflowRepository,
        exec_client: ExecutionServiceClient,
        notifier: NotificationClient,
    ):
        self.repo = repo
        self.exec_client = exec_client
        self.notifier = notifier

    # PUBLIC_INTERFACE
    async def create_workflow(self, req: WorkflowCreateRequest) -> Workflow:
        """Create a new workflow and queue initial executions."""
        stages = req.stages or DEFAULT_STAGES_BY_DOMAIN[req.domain]
        wf = Workflow(
            id=new_workflow_id(),
            correlate_run_id=req.correlate_run_id,
            git=req.git,
            domain=req.domain,
            stages=stages,
            status=WorkflowStatus.CREATED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            stage_results=init_stage_results(stages),
            metadata=req.metadata or {},
            notification=req.notification,
        )
        self.repo.create(wf)

        # Notify start if configured
        if req.notification and req.notification.on_start:
            await self.notifier.notify(
                req.notification,
                f"Workflow {wf.id} created for {req.git.repository}@{req.git.commit_sha}",
            )

        # Fire-and-forget triggers for each stage (simulate queueing)
        asyncio.create_task(self._kickoff_stages(wf.id))

        return wf

    async def _kickoff_stages(self, workflow_id: str) -> None:
        wf = self.repo.get(workflow_id)
        if not wf:
            return

        # Update status to queued
        wf.status = WorkflowStatus.QUEUED
        wf.updated_at = datetime.utcnow()
        self.repo.update(wf)

        # Sequential for simplicity; can be parallelized with dependencies if needed.
        for s in wf.stages:
            # mark running
            sr = wf.stage_results[s.value]
            sr.status = StageStatus.RUNNING
            sr.started_at = datetime.utcnow()
            wf.stage_results[s.value] = sr
            wf.status = compute_overall_status(wf.stage_results)
            wf.updated_at = datetime.utcnow()
            self.repo.update(wf)

            try:
                executor_ref = await self.exec_client.trigger_stage(
                    wf.id, s, wf.git, wf.metadata
                )
                sr.executor_ref = executor_ref
                # Simulate execution finishing after short delay
                await asyncio.sleep(0.05)
                sr.status = StageStatus.SUCCEEDED
                sr.finished_at = datetime.utcnow()
                sr.duration_ms = (
                    int((sr.finished_at - sr.started_at).total_seconds() * 1000)
                    if sr.started_at
                    else None
                )
                wf.stage_results[s.value] = sr
            except Exception as exc:  # noqa: BLE001
                sr.status = StageStatus.FAILED
                sr.error_message = str(exc)
                sr.finished_at = datetime.utcnow()
                wf.stage_results[s.value] = sr

            wf.status = compute_overall_status(wf.stage_results)
            wf.updated_at = datetime.utcnow()
            self.repo.update(wf)

        # Notify finish
        if wf.notification and wf.notification.on_finish:
            ok = wf.status == WorkflowStatus.SUCCEEDED
            await self.notifier.notify(
                wf.notification,
                f"Workflow {wf.id} finished with status={wf.status.value}. ok={ok}",
            )

    # PUBLIC_INTERFACE
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get workflow by id."""
        return self.repo.get(workflow_id)

    # PUBLIC_INTERFACE
    def list_workflows(
        self,
        *,
        script_path: Optional[str] = None,
        domain: Optional[str] = None,
        author: Optional[str] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
        stage: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Workflow]:
        """List workflows by filters."""
        dom = None
        if domain:
            from .models import Domain

            dom = Domain(domain)

        stg = None
        if stage:
            from .models import CertificationStage as StageEnum

            stg = StageEnum(stage)

        return self.repo.list(
            script_path=script_path,
            domain=dom,
            author=author,
            branch=branch,
            commit=commit,
            stage=stg,
            status=status,
            limit=limit,
            offset=offset,
        )

    # PUBLIC_INTERFACE
    def update_stage_status(
        self, workflow_id: str, req: WorkflowUpdateStatusRequest
    ) -> Optional[Workflow]:
        """Update a stage status, typically via callback from ExecutionService."""
        wf = self.repo.get(workflow_id)
        if not wf:
            return None
        sr = wf.stage_results.get(req.stage.value)
        if not sr:
            sr = StageResult(stage=req.stage, status=StageStatus.PENDING)
        sr.status = req.status
        if req.logs_url:
            sr.logs_url = req.logs_url
        if req.metrics is not None:
            sr.metrics = req.metrics
        if req.artifacts is not None:
            sr.artifacts = req.artifacts
        if req.error_message:
            sr.error_message = req.error_message
        if req.executor_ref:
            sr.executor_ref = req.executor_ref

        # manage timestamps
        if req.status == StageStatus.RUNNING:
            sr.started_at = datetime.utcnow()
        if req.status in (
            StageStatus.SUCCEEDED,
            StageStatus.FAILED,
            StageStatus.SKIPPED,
            StageStatus.CANCELLED,
        ):
            sr.finished_at = datetime.utcnow()
            if sr.started_at:
                sr.duration_ms = int(
                    (sr.finished_at - sr.started_at).total_seconds() * 1000
                )

        wf.stage_results[req.stage.value] = sr
        wf.status = compute_overall_status(wf.stage_results)
        wf.updated_at = datetime.utcnow()
        self.repo.update(wf)
        return wf
