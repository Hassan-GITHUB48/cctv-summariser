"""Report generation tests with a fake Anthropic client (no network, no cost)."""

from types import SimpleNamespace
from typing import Any

import pytest

from pipeline.incidents import Candidate
from pipeline.report import IncidentReport, ReportError, build_payload, generate_report

META = {"duration_s": 60.0}
SAMPLING = {"mode": "hybrid", "max_gap_s": 2.0}
CANDS = [Candidate("C1", "person", 10.0, 44.0, 18, 1, 0.9, "f.jpg", ["prolonged_presence"])]

GOOD = {
    "summary": "One person stayed for 34 seconds.",
    "incidents": [
        {
            "start_s": 10,
            "end_s": 44,
            "title": "Person loitering",
            "description": "A person remained in view.",
            "severity": 3,
            "recommended_action": "Review footage 00:10-00:44",
            "candidate_ids": ["C1"],
        }
    ],
}


class FakeClient:
    """Mimics ``client.beta.messages.parse``; each call returns the next scripted reply."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, str):  # raw text: validate like the SDK does (raises on bad JSON)
            return SimpleNamespace(stop_reason="end_turn", parsed_output=IncidentReport.model_validate_json(reply))
        if isinstance(reply, SimpleNamespace):
            return reply
        return SimpleNamespace(stop_reason="end_turn", parsed_output=IncidentReport.model_validate(reply))


def test_valid_report_first_try() -> None:
    client = FakeClient(GOOD)
    report, model = generate_report(CANDS, META, SAMPLING, client=client, model="test-model")
    assert report.incidents[0].severity == 3
    assert model == "test-model" and len(client.calls) == 1
    assert client.calls[0]["output_format"] is IncidentReport


def test_retries_once_on_invalid_json_then_succeeds() -> None:
    client = FakeClient('{"summary": "trunc', GOOD)
    report, _ = generate_report(CANDS, META, SAMPLING, client=client, model="m")
    assert len(client.calls) == 2
    assert "previous attempt was rejected" in client.calls[1]["messages"][0]["content"]
    assert report.summary.startswith("One person")


def test_fails_cleanly_after_two_invalid_replies() -> None:
    bad_severity = {**GOOD, "incidents": [{**GOOD["incidents"][0], "severity": 9}]}
    client = FakeClient(bad_severity, bad_severity)
    with pytest.raises(ReportError, match="invalid report twice"):
        generate_report(CANDS, META, SAMPLING, client=client, model="m")
    assert len(client.calls) == 2


def test_rejects_ungrounded_incidents() -> None:
    made_up = {**GOOD, "incidents": [{**GOOD["incidents"][0], "candidate_ids": ["C99"]}]}
    client = FakeClient(made_up, made_up)
    with pytest.raises(ReportError, match="unknown"):
        generate_report(CANDS, META, SAMPLING, client=client, model="m")


def test_refusal_is_not_retried() -> None:
    client = FakeClient(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(ReportError, match="declined"):
        generate_report(CANDS, META, SAMPLING, client=client, model="m")
    assert len(client.calls) == 1


def test_no_candidates_skips_llm() -> None:
    client = FakeClient()
    report, _ = generate_report([], META, SAMPLING, client=client, model="m")
    assert report.incidents == [] and client.calls == []


def test_fallbacks_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(GOOD, GOOD)
    monkeypatch.setenv("ANTHROPIC_FALLBACKS", "default")
    generate_report(CANDS, META, SAMPLING, client=client, model="m")
    monkeypatch.setenv("ANTHROPIC_FALLBACKS", "")
    generate_report(CANDS, META, SAMPLING, client=client, model="m")
    assert client.calls[0]["fallbacks"] == "default"
    assert "fallbacks" not in client.calls[1] and "betas" not in client.calls[1]


def test_payload_is_compact() -> None:
    payload = build_payload(CANDS, META, SAMPLING)
    assert "frame_path" not in payload["candidates"][0]
    assert payload["candidates"][0]["flags"] == ["prolonged_presence"]
