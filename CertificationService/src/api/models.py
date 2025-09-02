from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

# PUBLIC_INTERFACE
class CertificationStage(str, Enum):
    """Enumeration of supported certification stages."""
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    FUNCTIONAL = "functional"
    E2E = "e2e"
    SOAK = "soak"
    PERFORMANCE = "performance"


# PUBLIC_INTERFACE
class Domain(str, Enum):
    """Enumeration of supported domains."""
    CORE = "core"
    TRANSPORT = "transport"
    BANKING = "banking"
    HEALTHCARE = "healthcare"


# PUBLIC_INTERFACE
class GitInfo(BaseModel):
    """Git repository info associated with a certification workflow."""
    repository: str = Field(..., description="Full git repository URL or path (e.g., git@gitlab.com:org/repo.git)")
    folder: Optional[str] = Field(None, description="Relative folder inside the repository where scripts live")
    branch: str = Field(..., description="Git branch for the workflow")
    commit_sha: str = Field(..., description="Commit SHA associated with the workflow")
    author: Optional[str] = Field(None, description="Author of the commit or workflow requester")


# PUBLIC_INTERFACE
class NotificationConfig(BaseModel):
    """Optional notification configuration for the workflow."""
    webhook_url: Optional[HttpUrl] = Field(None, description="Webhook URL for posting notifications")
    email: Optional[str] = Field(None, description="Email to notify upon completion or failures")
    slack_channel: Optional[str] = Field(None, description="Slack channel for notifications")
    on_start: bool = Field(False, description="Send notification when the workflow starts")
    on_finish: bool = Field(True, description="Send notification when the workflow finishes")
    on_failure: bool = Field(True, description="Send notification on any stage failure")


# PUBLIC_INTERFACE
class WorkflowCreateRequest(BaseModel):
    """Request model to create a certification workflow."""
    git: GitInfo = Field(..., description="Git parameters for the workflow")
    domain: Domain = Field(..., description="Domain for certification")
    stages: Optional[List[CertificationStage]] = Field(
        None, description="Specific stages to run; if omitted, run domain defaults"
    )
    metadata: Optional[Dict[str, str]] = Field(None, description="Arbitrary metadata for traceability")
    notification: Optional[NotificationConfig] = Field(None, description="Notification configuration override")
    correlate_run_id: Optional[str] = Field(
        None, description="Optional correlation/run id to group multiple workflow requests"
    )


# PUBLIC_INTERFACE
class StageStatus(str, Enum):
    """Enumeration of status for a certification stage."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


# PUBLIC_INTERFACE
class StageResult(BaseModel):
    """Result details for a stage execution."""
    stage: CertificationStage = Field(..., description="Stage name")
    status: StageStatus = Field(..., description="Current status of the stage")
    started_at: Optional[datetime] = Field(None, description="Stage start time")
    finished_at: Optional[datetime] = Field(None, description="Stage finish time")
    duration_ms: Optional[int] = Field(None, description="Execution duration in milliseconds")
    logs_url: Optional[str] = Field(None, description="Link to logs (e.g., Loki/Grafana)")
    metrics: Optional[Dict[str, float]] = Field(None, description="Collected metrics (e.g., cpu, mem)")
    artifacts: Optional[Dict[str, str]] = Field(None, description="Artifact references keyed by name")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    executor_ref: Optional[str] = Field(None, description="Reference returned by the Execution Service")


# PUBLIC_INTERFACE
class WorkflowStatus(str, Enum):
    """Status for a workflow."""
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# PUBLIC_INTERFACE
class Workflow(BaseModel):
    """Represents a certification workflow instance."""
    id: str = Field(..., description="Workflow identifier")
    correlate_run_id: Optional[str] = Field(None, description="Correlation id to group workflows")
    git: GitInfo = Field(..., description="Git information")
    domain: Domain = Field(..., description="Domain")
    stages: List[CertificationStage] = Field(..., description="Stages planned for execution")
    status: WorkflowStatus = Field(..., description="Overall workflow status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    stage_results: Dict[str, StageResult] = Field(
        default_factory=dict, description="Map of stage -> StageResult"
    )
    metadata: Dict[str, str] = Field(default_factory=dict, description="Metadata for traceability")
    notification: Optional[NotificationConfig] = Field(None, description="Notification configuration in effect")


# PUBLIC_INTERFACE
class WorkflowUpdateStatusRequest(BaseModel):
    """Request model for updating a stage status (typically from Execution Service callbacks)."""
    stage: CertificationStage = Field(..., description="Stage being updated")
    status: StageStatus = Field(..., description="New status for the stage")
    logs_url: Optional[str] = Field(None, description="Optional logs link")
    metrics: Optional[Dict[str, float]] = Field(None, description="Optional metrics")
    artifacts: Optional[Dict[str, str]] = Field(None, description="Optional artifacts")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    executor_ref: Optional[str] = Field(None, description="Executor reference id")


# PUBLIC_INTERFACE
class QueryParams(BaseModel):
    """Common query params for history/results endpoints."""
    script_path: Optional[str] = Field(None, description="Script relative path")
    domain: Optional[Domain] = Field(None, description="Filter by domain")
    author: Optional[str] = Field(None, description="Filter by author")
    branch: Optional[str] = Field(None, description="Filter by branch")
    commit: Optional[str] = Field(None, description="Filter by commit SHA")
    stage: Optional[CertificationStage] = Field(None, description="Filter by stage")
    status: Optional[Literal["succeeded", "failed", "running", "partial", "created", "queued"]] = Field(
        None, description="Filter by workflow status (string literal)"
    )
    limit: int = Field(50, description="Max number of records", ge=1, le=500)
    offset: int = Field(0, description="Offset for pagination", ge=0)


# PUBLIC_INTERFACE
class HealthReport(BaseModel):
    """Self monitoring/health information."""
    service: str = Field(..., description="Service name")
    status: Literal["healthy", "degraded", "unhealthy"] = Field(..., description="Overall status")
    version: str = Field(..., description="Service version")
    time: datetime = Field(..., description="Report time")
    workers_busy: int = Field(..., description="Simulated busy worker count")
    queue_depth: int = Field(..., description="Simulated queue depth")
    notes: Optional[str] = Field(None, description="Additional notes")
