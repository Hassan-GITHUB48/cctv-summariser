"""Response models: they validate API output and document it in the OpenAPI schema (/docs)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from pipeline.report import Incident

StageState = Literal["pending", "running", "done", "failed"]


class JobCreated(BaseModel):
    job_id: str
    status: str


class JobSummary(BaseModel):
    job_id: str
    source: str
    status: str
    incident_count: int
    created_at: datetime
    updated_at: datetime


class Stage(BaseModel):
    name: Literal["ingesting", "keyframes", "detecting", "reporting"]
    state: StageState


class JobStatus(BaseModel):
    job_id: str
    source: str
    status: str
    error: str | None
    failed_stage: str | None
    progress: float  # 0..1, fraction of stages completed
    stages: list[Stage]
    meta: dict | None
    sampling: dict | None
    timings: dict | None
    created_at: datetime
    updated_at: datetime


class EventOut(BaseModel):
    timestamp_s: float
    frame_index: int
    label: str
    confidence: float
    bbox: list[int]
    frame_url: str


class ReportOut(BaseModel):
    job_id: str
    model: str
    summary: str
    incidents: list[Incident]
    created_at: datetime
