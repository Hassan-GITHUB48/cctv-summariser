"""Stage 4: turn candidate incidents into a validated, timestamped report with Claude."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError, model_validator

from pipeline.incidents import Candidate

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """You are a security analyst reviewing automated CCTV analytics.
You receive candidate incidents produced by an object detector (people and vehicles) on sampled
frames. Write a concise incident report for a security guard.

Rules:
- Only describe what the evidence supports. Never invent identities, intent, or objects not listed.
- Merge candidates that clearly describe one situation (e.g. a person arriving with a bicycle).
- Every incident must cite the candidate IDs it is based on and use their time range.
- Severity: 1 = routine activity, 3 = worth a look, 5 = needs immediate attention.
  Raise severity for prolonged presence, groups, or activity in unusual hours; keep ordinary
  passers-by and passing traffic at 1-2.
- Recommended action must be concrete (e.g. "Review footage 00:40-00:49", "No action needed").
- Detections come from sampled frames, so short events between samples may be missed; say so
  in the summary if coverage is a limitation."""


class Incident(BaseModel):
    """One incident in the report, grounded in candidate IDs."""

    start_s: float = Field(ge=0, description="Start time in seconds from the start of the video")
    end_s: float = Field(ge=0, description="End time in seconds from the start of the video")
    title: str = Field(description="Short headline, e.g. 'Person loitering near entrance'")
    description: str
    severity: int = Field(ge=1, le=5)
    recommended_action: str
    candidate_ids: list[str] = Field(description="IDs of the candidates this incident is based on")

    @model_validator(mode="after")
    def _times_ordered(self) -> Incident:
        if self.end_s < self.start_s:
            raise ValueError("end_s must be >= start_s")
        return self


class IncidentReport(BaseModel):
    """The LLM's full response."""

    summary: str = Field(description="2-4 sentence plain-English overview of the footage")
    incidents: list[Incident]


class ReportError(RuntimeError):
    """Raised when a valid report could not be produced."""


def build_payload(candidates: list[Candidate], meta: dict, sampling: dict) -> dict:
    """Compact, structured summary sent to the LLM (no images, no raw detections)."""
    return {
        "video": {"duration_s": round(meta["duration_s"], 1), "sampling": sampling},
        "candidates": [
            {k: v for k, v in c.to_dict().items() if k != "frame_path" and v is not None}
            for c in candidates
        ],
    }


def check_grounded(report: IncidentReport, candidates: list[Candidate], duration_s: float) -> None:
    """Reject reports that cite unknown candidates or fall outside the video."""
    known = {c.id for c in candidates}
    for inc in report.incidents:
        unknown = set(inc.candidate_ids) - known
        if not inc.candidate_ids or unknown:
            raise ValueError(f"Incident '{inc.title}' cites unknown or no candidates: {sorted(unknown)}")
        if inc.end_s > duration_s + 1:
            raise ValueError(f"Incident '{inc.title}' ends at {inc.end_s}s, after the video ends")


def _call_llm(client: anthropic.Anthropic, model: str, prompt: str) -> IncidentReport:
    kwargs: dict[str, Any] = {}
    if fallbacks := os.getenv("ANTHROPIC_FALLBACKS", "default"):
        kwargs = {"betas": [FALLBACK_BETA], "fallbacks": fallbacks}
    response = client.beta.messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
        output_format=IncidentReport,  # schema-constrained output, validated by Pydantic
        **kwargs,
    )
    if response.stop_reason == "refusal":
        raise ReportError("Model declined to produce a report")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise ValueError(f"Incomplete response (stop_reason={response.stop_reason})")
    return response.parsed_output


def generate_report(
    candidates: list[Candidate],
    meta: dict,
    sampling: dict,
    client: anthropic.Anthropic | None = None,
    model: str | None = None,
) -> tuple[IncidentReport, str]:
    """Ask the LLM for a report; retry once on invalid output, then raise ReportError.

    Returns the validated report and the model name used.
    """
    model = model or os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    if not candidates:  # nothing to analyse: skip the API call entirely
        return IncidentReport(summary="No people or vehicles were detected in the footage.", incidents=[]), model

    client = client or anthropic.Anthropic()
    prompt = "Candidate incidents (JSON):\n" + json.dumps(build_payload(candidates, meta, sampling), indent=1)
    error: Exception | None = None
    for attempt in (1, 2):
        attempt_prompt = prompt if error is None else (
            f"{prompt}\n\nA previous attempt was rejected: {error}\nFix this in your answer."
        )
        try:
            report = _call_llm(client, model, attempt_prompt)
            check_grounded(report, candidates, meta["duration_s"])
            log.info("Report generated on attempt %d with %d incidents", attempt, len(report.incidents))
            return report, model
        except (ValidationError, ValueError) as exc:
            log.warning("Invalid report on attempt %d: %s", attempt, exc)
            error = exc
        except anthropic.APIError as exc:  # SDK already retried transient errors
            raise ReportError(f"Anthropic API error: {exc}") from exc
    raise ReportError(f"LLM returned an invalid report twice; last error: {error}")
