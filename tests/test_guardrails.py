"""Tests for the Bedrock guardrails layer (packages/llm/guardrails.py).

These never touch AWS: the disabled path is a pure no-op, and the enabled
path is exercised by stubbing `_apply` (the one boto call) with canned
ApplyGuardrail responses. So they run under `make check` with no creds.
"""
from __future__ import annotations

import pytest

from llm import guardrails
from llm.guardrails import (
    _REFUSAL_CONTENT,
    _REFUSAL_GROUNDING,
    _REFUSAL_TOPIC,
    GuardrailOutcome,
    guard_input,
    guard_output,
)
from settings import Settings


def _settings(**kw) -> Settings:
    return Settings(**kw)


@pytest.fixture
def enabled(monkeypatch):
    """Configure a guardrail ID so the layer is 'on'."""
    s = _settings(bedrock_guardrail_id="gr-test", bedrock_guardrail_version="DRAFT")
    monkeypatch.setattr(guardrails, "get_settings", lambda: s)
    return s


@pytest.fixture
def disabled(monkeypatch):
    s = _settings(bedrock_guardrail_id=None)
    monkeypatch.setattr(guardrails, "get_settings", lambda: s)
    return s


# ── Gating: no guardrail configured → pure pass-through ────────────────────


def test_disabled_input_is_passthrough(disabled, monkeypatch):
    # _apply must never be called when disabled.
    monkeypatch.setattr(
        guardrails, "_apply", lambda *a, **k: pytest.fail("should not call AWS")
    )
    out = guard_input("anything")
    assert out.text == "anything"
    assert not out.intervened and not out.blocked


def test_disabled_output_is_passthrough(disabled, monkeypatch):
    monkeypatch.setattr(
        guardrails, "_apply", lambda *a, **k: pytest.fail("should not call AWS")
    )
    out = guard_output("q", "the answer", "some source")
    assert out.text == "the answer"
    assert not out.intervened


# ── Interpretation of ApplyGuardrail responses ─────────────────────────────


def test_no_intervention_passes_through():
    resp = {"action": "NONE"}
    out = guardrails._interpret(resp, "answer", mask_sensitive=True)
    assert out.text == "answer"
    assert not out.intervened


def test_grounding_block_returns_refusal():
    resp = {
        "action": "GUARDRAIL_INTERVENED",
        "assessments": [
            {
                "contextualGroundingPolicy": {
                    "filters": [
                        {"type": "GROUNDING", "action": "BLOCKED", "score": 0.1},
                        {"type": "RELEVANCE", "action": "NONE", "score": 0.9},
                    ]
                }
            }
        ],
    }
    out = guardrails._interpret(resp, "ungrounded answer", mask_sensitive=True)
    assert out.blocked
    assert out.text == _REFUSAL_GROUNDING
    assert any("ungrounded" in r for r in out.reasons)


def test_denied_topic_returns_topic_refusal():
    resp = {
        "action": "GUARDRAIL_INTERVENED",
        "assessments": [
            {
                "topicPolicy": {
                    "topics": [
                        {"name": "JudicialOutcomePrediction", "action": "BLOCKED"}
                    ]
                }
            }
        ],
    }
    out = guardrails._interpret(resp, "the judge will grant it", mask_sensitive=True)
    assert out.blocked
    assert out.text == _REFUSAL_TOPIC


def test_content_filter_returns_generic_refusal():
    resp = {
        "action": "GUARDRAIL_INTERVENED",
        "assessments": [
            {"contentPolicy": {"filters": [{"type": "HATE", "action": "BLOCKED"}]}}
        ],
    }
    out = guardrails._interpret(resp, "nasty text", mask_sensitive=True)
    assert out.blocked
    assert out.text == _REFUSAL_CONTENT


def test_pii_on_output_is_masked_not_blocked():
    resp = {
        "action": "GUARDRAIL_INTERVENED",
        "assessments": [
            {
                "sensitiveInformationPolicy": {
                    "piiEntities": [
                        {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "ANONYMIZED"}
                    ]
                }
            }
        ],
        "outputs": [{"text": "Your SSN is {US_SOCIAL_SECURITY_NUMBER}."}],
    }
    out = guardrails._interpret(
        resp, "Your SSN is 123-45-6789.", mask_sensitive=True
    )
    assert out.masked and not out.blocked
    assert out.text == "Your SSN is {US_SOCIAL_SECURITY_NUMBER}."


def test_pii_on_input_is_ignored():
    # mask_sensitive=False (input side): a PII detection must not block the
    # litigant from citing their own data.
    resp = {
        "action": "GUARDRAIL_INTERVENED",
        "assessments": [
            {
                "sensitiveInformationPolicy": {
                    "piiEntities": [
                        {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "ANONYMIZED"}
                    ]
                }
            }
        ],
        "outputs": [{"text": "masked"}],
    }
    out = guardrails._interpret(resp, "my ssn is 123-45-6789", mask_sensitive=False)
    assert not out.blocked and not out.masked
    assert out.text == "my ssn is 123-45-6789"


def test_pii_blocked_action_is_a_hard_block_on_output():
    resp = {
        "action": "GUARDRAIL_INTERVENED",
        "assessments": [
            {
                "sensitiveInformationPolicy": {
                    "piiEntities": [{"type": "PASSWORD", "action": "BLOCKED"}]
                }
            }
        ],
    }
    out = guardrails._interpret(resp, "secret", mask_sensitive=True)
    assert out.blocked


# ── Fail-open: an API error must not break chat ────────────────────────────


def test_fail_open_when_apply_errors(enabled, monkeypatch):
    # _apply returns None on any boto error (it swallows + logs).
    monkeypatch.setattr(guardrails, "_apply", lambda *a, **k: None)
    out = guard_output("q", "the answer", "source")
    assert out.text == "the answer"
    assert not out.intervened


# ── End-to-end through the public functions (stubbed boto) ─────────────────


def test_guard_output_blocks_ungrounded(enabled, monkeypatch):
    captured = {}

    def fake_apply(source, content):
        captured["source"] = source
        captured["content"] = content
        return {
            "action": "GUARDRAIL_INTERVENED",
            "assessments": [
                {
                    "contextualGroundingPolicy": {
                        "filters": [{"type": "GROUNDING", "action": "BLOCKED"}]
                    }
                }
            ],
        }

    monkeypatch.setattr(guardrails, "_apply", fake_apply)
    out = guard_output("What is alimony?", "Made-up answer.", "Conn. Gen. Stat...")
    assert out.blocked
    assert captured["source"] == "OUTPUT"
    # grounding source + query + guard_content qualifiers all present.
    quals = [c["text"].get("qualifiers", []) for c in captured["content"]]
    assert ["grounding_source"] in quals
    assert ["query"] in quals
    assert ["guard_content"] in quals


def test_guard_output_omits_grounding_qualifier_when_no_source(enabled, monkeypatch):
    captured = {}

    def fake_apply(source, content):
        captured["content"] = content
        return {"action": "NONE"}

    monkeypatch.setattr(guardrails, "_apply", fake_apply)
    guard_output("hi", "Hello!", "")  # empty grounding source
    quals = [c["text"].get("qualifiers", []) for c in captured["content"]]
    assert ["grounding_source"] not in quals
    assert ["guard_content"] in quals


def test_passthrough_constructor():
    out = GuardrailOutcome.passthrough("x")
    assert out.text == "x" and not out.intervened
