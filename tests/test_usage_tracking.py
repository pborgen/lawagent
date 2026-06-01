"""Tests for LLM usage capture (llm.usage) and pricing (llm.pricing).

These are pure-Python and offline — no DB, no provider calls. They cover
the three moving parts the metering relies on:

  * the chat callback reading `usage_metadata` off a response,
  * the embeddings wrapper recording an estimated token tally, and
  * the token → dollar conversion.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from langchain_core.embeddings import Embeddings

from llm.embeddings import _MeteredEmbeddings
from llm.pricing import cost_usd
from llm.usage import UsageCallbackHandler, record_usage


def _fake_llm_result(input_tokens: int, output_tokens: int, model: str):
    """Mimic a LangChain LLMResult carrying usage on the message."""
    message = SimpleNamespace(
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
    )
    generation = SimpleNamespace(message=message)
    return SimpleNamespace(
        generations=[[generation]],
        llm_output={"model_name": model},
    )


def test_callback_records_chat_usage():
    handler = UsageCallbackHandler()
    with record_usage() as events:
        handler.on_llm_end(_fake_llm_result(120, 30, "claude-opus-4-7"))

    assert len(events) == 1
    ev = events[0]
    assert ev.kind == "chat"
    assert ev.model == "claude-opus-4-7"
    assert ev.input_tokens == 120
    assert ev.output_tokens == 30
    assert ev.total_tokens == 150
    assert ev.tokens_estimated is False


def test_callback_marks_estimated_when_no_usage():
    """A response with no usage_metadata → zero tokens, flagged estimated."""
    handler = UsageCallbackHandler()
    bare = SimpleNamespace(generations=[[SimpleNamespace(message=SimpleNamespace())]],
                           llm_output=None)
    with record_usage() as events:
        handler.on_llm_end(bare)
    assert events[0].tokens_estimated is True
    assert events[0].total_tokens == 0


def test_no_recorder_is_a_noop():
    """Outside a record_usage() block, callbacks must not raise."""
    UsageCallbackHandler().on_llm_end(_fake_llm_result(1, 1, "x"))  # no error


class _FakeEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[0.0] for _ in texts]

    def embed_query(self, text):
        return [0.0]


def test_embeddings_wrapper_records_estimated_tokens():
    wrapped = _MeteredEmbeddings(
        _FakeEmbeddings(), provider="voyage", model="voyage-3"
    )
    with record_usage() as events:
        wrapped.embed_query("a query with some words to estimate")
        wrapped.embed_documents(["doc one", "doc two"])

    assert len(events) == 2
    assert all(e.kind == "embedding" for e in events)
    assert all(e.provider == "voyage" and e.model == "voyage-3" for e in events)
    assert all(e.output_tokens == 0 for e in events)
    assert all(e.tokens_estimated for e in events)
    assert all(e.input_tokens > 0 for e in events)


def test_cost_usd_known_model():
    # Opus: $15 / Mtok input, $75 / Mtok output.
    assert cost_usd("claude-opus-4-7", 1_000_000, 1_000_000) == Decimal("90.000000")
    # Case-insensitive lookup.
    assert cost_usd("CLAUDE-OPUS-4-7", 1_000_000, 0) == Decimal("15.000000")


def test_cost_usd_unknown_model_is_none():
    assert cost_usd("some-local-model", 1000, 1000) is None
