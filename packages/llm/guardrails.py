"""Amazon Bedrock Guardrails — the single place the app validates LLM output.

This mirrors the boundary `llm/chat.py` draws for model construction:
nothing in `apps/` calls the Bedrock guardrail API directly. The agent
feeds its answer — and the passages it actually retrieved — through
`guard_output()`, and the user's question through `guard_input()`.

What the configured guardrail (infra/terraform/guardrails.tf) checks, and
how this module reacts:

- **Contextual grounding** — is the answer grounded in the retrieved
  passages and relevant to the question? This is the anti-hallucination
  centerpiece: an ungrounded answer is the failure mode that kills a
  citation tool, so a grounding intervention **blocks** (refusal).
- **Denied topics** — predicting how a specific judge will rule,
  non-Connecticut-family-law questions → **block**.
- **Content / prompt-attack filters** — toxicity on the answer, jailbreak
  attempts on the question → **block**.
- **Sensitive information (PII)** — PII in the *answer* is **masked**
  (we keep the answer, swapping in Bedrock's anonymized text). PII in the
  user's own *question* is left alone — the litigant may legitimately
  type their own SSN, address, etc.

Two deliberate operational choices:

1. **Gated on `LAWAGENT_BEDROCK_GUARDRAIL_ID`.** Unset (local dev, CI,
   `make check`) → every function is a pass-through and never imports boto
   or needs AWS creds.
2. **Fail-open on API error.** If the `ApplyGuardrail` call itself errors
   (throttling, endpoint down), we log loudly and return the answer
   unchanged rather than breaking chat. The system prompt's grounding
   rules remain the primary defense; the guardrail is defense-in-depth.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from settings import get_settings


logger = logging.getLogger(__name__)


# Refusals shown to the user when a hard policy fires. Kept terse and
# non-legal — we're declining, not advising.
_REFUSAL_GROUNDING = (
    "I can't give a grounded answer to that from the Connecticut materials "
    "I retrieved. Try rephrasing, or narrowing to a specific statute, form, "
    "or issue so I can find supporting text."
)
_REFUSAL_TOPIC = (
    "That's outside what this assistant will answer — for example predicting "
    "how a particular judge or court will rule, or questions outside "
    "Connecticut family / divorce law."
)
_REFUSAL_CONTENT = "I can't help with that request."


@dataclass
class GuardrailOutcome:
    """Result of running one guardrail check.

    `text` is what callers should use going forward: the original text when
    nothing fired, Bedrock's anonymized text when PII was masked, or a
    refusal message when a hard policy blocked it.
    """

    text: str
    intervened: bool = False
    blocked: bool = False
    masked: bool = False
    reasons: list[str] = field(default_factory=list)

    @classmethod
    def passthrough(cls, text: str) -> "GuardrailOutcome":
        return cls(text=text)


@lru_cache(maxsize=1)
def _client() -> Any:
    """Cached bedrock-runtime client.

    Region comes from `LAWAGENT_BEDROCK_GUARDRAIL_REGION`, else boto3's
    standard chain (AWS_REGION). In App Runner this resolves to the
    bedrock-runtime VPC endpoint — `ApplyGuardrail` rides the same
    interface endpoint as `InvokeModel` (see infra/terraform/network.tf).
    """
    import boto3  # imported lazily so the no-guardrail path needs no boto

    region = get_settings().bedrock_guardrail_region or None
    return boto3.client("bedrock-runtime", region_name=region)


def _apply(source: str, content: list[dict]) -> dict | None:
    """Call ApplyGuardrail. Returns the raw response, or None on any error.

    Fail-open: an exception here (throttling, endpoint unreachable, bad
    config) is logged and swallowed so a guardrail hiccup never breaks the
    chat. Returning None makes the caller treat it as "nothing fired".
    """
    s = get_settings()
    try:
        return _client().apply_guardrail(
            guardrailIdentifier=s.bedrock_guardrail_id,
            guardrailVersion=s.bedrock_guardrail_version,
            source=source,
            content=content,
        )
    except Exception:  # noqa: BLE001 - availability over strictness
        logger.warning(
            "Bedrock ApplyGuardrail (%s) failed; passing content through "
            "un-guarded.",
            source,
            exc_info=True,
        )
        return None


def _policy_blocked(assessment: dict, key: str) -> list[str]:
    """Topic/content/word policies: collect the names of entries that BLOCKED."""
    pol = assessment.get(key)
    if not pol:
        return []
    reasons: list[str] = []
    # Each policy nests a list under a type-specific key; the entries share
    # an `action` field we filter on. We don't hard-code every shape — we
    # walk any list of dicts and keep those that were acted on.
    for entries in pol.values():
        if not isinstance(entries, list):
            continue
        for e in entries:
            if isinstance(e, dict) and e.get("action") in ("BLOCKED", "DENIED"):
                reasons.append(
                    e.get("name") or e.get("type") or e.get("filterStrength") or key
                )
    return reasons


def _grounding_blocked(assessment: dict) -> list[str]:
    """Contextual grounding: a filter (GROUNDING/RELEVANCE) below threshold."""
    pol = assessment.get("contextualGroundingPolicy")
    if not pol:
        return []
    reasons: list[str] = []
    for f in pol.get("filters", []):
        if isinstance(f, dict) and f.get("action") == "BLOCKED":
            reasons.append(f"ungrounded:{f.get('type', 'grounding').lower()}")
    return reasons


def _sensitive(assessment: dict) -> tuple[list[str], bool]:
    """PII policy. Returns (anonymized entity types, any_blocked).

    ANONYMIZED entities are masked in the response's `outputs` text; a
    BLOCKED entity means the guardrail refused outright.
    """
    pol = assessment.get("sensitiveInformationPolicy")
    if not pol:
        return [], False
    anonymized: list[str] = []
    any_blocked = False
    for group in ("piiEntities", "regexes"):
        for e in pol.get(group, []):
            if not isinstance(e, dict):
                continue
            action = e.get("action")
            label = e.get("type") or e.get("name") or "PII"
            if action == "ANONYMIZED":
                anonymized.append(label)
            elif action == "BLOCKED":
                any_blocked = True
                anonymized.append(label)
    return anonymized, any_blocked


def _interpret(
    resp: dict | None, original: str, *, mask_sensitive: bool
) -> GuardrailOutcome:
    """Turn a raw ApplyGuardrail response into an actionable outcome.

    `mask_sensitive=True` (output side): PII → use Bedrock's masked text,
    not a block. `mask_sensitive=False` (input side): PII detections are
    ignored — we never block the litigant for citing their own data.
    """
    if not resp or resp.get("action") != "GUARDRAIL_INTERVENED":
        return GuardrailOutcome.passthrough(original)

    grounding: list[str] = []
    topic: list[str] = []
    content: list[str] = []
    masked: list[str] = []
    sensitive_blocked = False

    for a in resp.get("assessments", []):
        grounding += _grounding_blocked(a)
        topic += _policy_blocked(a, "topicPolicy")
        content += _policy_blocked(a, "contentPolicy")
        content += _policy_blocked(a, "wordPolicy")
        ents, blocked = _sensitive(a)
        sensitive_blocked = sensitive_blocked or blocked
        if mask_sensitive:
            masked += ents

    # Hard blocks, in priority order for picking the refusal message.
    if grounding or topic or content or (sensitive_blocked and mask_sensitive):
        if grounding:
            text = _REFUSAL_GROUNDING
        elif topic:
            text = _REFUSAL_TOPIC
        else:
            text = _REFUSAL_CONTENT
        reasons = grounding + topic + content + (["sensitive-info"] if sensitive_blocked else [])
        return GuardrailOutcome(
            text=text, intervened=True, blocked=True, reasons=reasons
        )

    if masked:
        return GuardrailOutcome(
            text=_masked_text(resp, original),
            intervened=True,
            masked=True,
            reasons=masked,
        )

    # Intervened on something we don't act on (e.g. input-side PII): pass through.
    return GuardrailOutcome.passthrough(original)


def _masked_text(resp: dict, original: str) -> str:
    """Pull the anonymized text Bedrock returns in `outputs`, else original."""
    for out in resp.get("outputs", []):
        text = out.get("text")
        if text:
            return text
    return original


def guard_input(question: str) -> GuardrailOutcome:
    """Check the user's question (prompt-attack, denied topics).

    No-op when no guardrail is configured. PII in the question is *not*
    acted on — the litigant may legitimately include their own data.
    """
    if not get_settings().guardrail_enabled() or not question.strip():
        return GuardrailOutcome.passthrough(question)
    resp = _apply("INPUT", [{"text": {"text": question}}])
    return _interpret(resp, question, mask_sensitive=False)


def guard_output(
    question: str, answer: str, grounding_source: str
) -> GuardrailOutcome:
    """Validate the agent's answer against the retrieved passages.

    `grounding_source` is the concatenated text of the chunks the agent
    actually retrieved. When it's empty (the agent answered without
    retrieving), we skip the grounding/relevance qualifiers so the
    grounding policy doesn't auto-fail benign replies — content, topic, and
    PII checks still run.
    """
    if not get_settings().guardrail_enabled() or not answer.strip():
        return GuardrailOutcome.passthrough(answer)

    content: list[dict] = []
    if grounding_source.strip():
        content.append(
            {"text": {"text": grounding_source, "qualifiers": ["grounding_source"]}}
        )
        if question.strip():
            content.append({"text": {"text": question, "qualifiers": ["query"]}})
    content.append({"text": {"text": answer, "qualifiers": ["guard_content"]}})

    resp = _apply("OUTPUT", content)
    return _interpret(resp, answer, mask_sensitive=True)
