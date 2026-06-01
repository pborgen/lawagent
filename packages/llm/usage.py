"""Per-request LLM usage capture.

Token usage is collected the same way the agent captures its retrieved
sources (see `agent/src/tools.py`): a `ContextVar` holds a per-request
list, and the model layer appends to it. Because models are only ever
built through this package (golden rule #1), this is the natural single
place to meter them — `apps/` never sees raw provider responses.

Two hook points feed the recorder:

  * `UsageCallbackHandler` — a LangChain callback the agent passes into
    `model.invoke(config=...)`. On `on_llm_end` it reads the response's
    `usage_metadata` (input/output tokens), which Anthropic, OpenAI and
    Bedrock all populate. Local/Ollama models that omit it are recorded
    with zero tokens.
  * `record_embedding()` — called by the embeddings wrapper
    (`embeddings.py`) on every embed call, since embedding token counts
    don't flow through LLM callbacks.

When no recorder is active (CLI runs, ingest without metering) both hooks
are no-ops, so nothing else has to change.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Literal, Optional

from langchain_core.callbacks import BaseCallbackHandler

UsageKind = Literal["chat", "embedding"]


@dataclass
class UsageEvent:
    """One metered model call. Token counts are best-effort.

    `tokens_estimated` is True when we didn't get real usage from the
    provider and fell back to a heuristic (embeddings, or chat models
    that don't report usage).
    """

    kind: UsageKind
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_estimated: bool = False

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# Per-request collector. The API's /chat handler activates this via
# `record_usage()` before invoking the agent and reads it after. A
# ContextVar (not a module global) so concurrent requests in FastAPI's
# threadpool never share each other's tallies.
_RECORDER: ContextVar[Optional[list[UsageEvent]]] = ContextVar(
    "llm_usage_recorder", default=None
)


@contextmanager
def record_usage() -> Iterator[list[UsageEvent]]:
    """Activate usage capture for the duration of the block.

    Yields the list that every model call inside the block appends to:

        with record_usage() as events:
            answer = ask(question)
        persist(events)
    """
    events: list[UsageEvent] = []
    token = _RECORDER.set(events)
    try:
        yield events
    finally:
        _RECORDER.reset(token)


def _emit(event: UsageEvent) -> None:
    """Append to the active recorder, or drop the event if none is set."""
    recorder = _RECORDER.get()
    if recorder is not None:
        recorder.append(event)


def record_embedding(
    *, provider: str, model: str, input_tokens: int, estimated: bool = True
) -> None:
    """Record one embedding call (output tokens are always zero)."""
    _emit(
        UsageEvent(
            kind="embedding",
            provider=provider,
            model=model,
            input_tokens=max(0, input_tokens),
            output_tokens=0,
            tokens_estimated=estimated,
        )
    )


def _usage_from_message(message: object) -> tuple[int, int] | None:
    """Pull (input, output) token counts off an AIMessage, if present.

    LangChain normalizes provider usage onto `AIMessage.usage_metadata`
    as `{"input_tokens", "output_tokens", "total_tokens"}` — the same
    shape across Anthropic/OpenAI/Bedrock. Returns None when absent.
    """
    meta = getattr(message, "usage_metadata", None)
    if not isinstance(meta, dict):
        return None
    return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))


class UsageCallbackHandler(BaseCallbackHandler):
    """Records chat-model token usage into the active recorder.

    A single shared instance is fine: it carries no per-request state and
    reads the recorder ContextVar at event time, so concurrent requests
    stay isolated. The default chat model name is resolved lazily from the
    active profile only as a fallback when the provider response omits it.
    """

    def on_llm_end(self, response, **kwargs) -> None:  # noqa: ANN001 - LangChain signature
        input_tokens = 0
        output_tokens = 0
        got_usage = False
        for batch in getattr(response, "generations", []) or []:
            for gen in batch:
                counts = _usage_from_message(getattr(gen, "message", None))
                if counts is not None:
                    input_tokens += counts[0]
                    output_tokens += counts[1]
                    got_usage = True

        model, provider = _active_chat_identity()
        llm_output = getattr(response, "llm_output", None)
        if isinstance(llm_output, dict):
            model = llm_output.get("model_name") or llm_output.get("model") or model

        _emit(
            UsageEvent(
                kind="chat",
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                # No usage on the response → the counts are zero, not real.
                tokens_estimated=not got_usage,
            )
        )


def _active_chat_identity() -> tuple[str, str]:
    """(model, provider) for the active profile's chat model."""
    from llm.profiles import get_active_profile

    chat = get_active_profile().chat
    return chat.model, chat.provider


# Shared, stateless handler instance reused across requests.
_HANDLER = UsageCallbackHandler()


def usage_callbacks() -> list[BaseCallbackHandler]:
    """Callbacks to pass into `model.invoke(config={"callbacks": ...})`.

    Always returns the handler; it no-ops when no recorder is active, so
    callers don't need to branch on whether metering is on.
    """
    return [_HANDLER]
