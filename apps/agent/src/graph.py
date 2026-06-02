from __future__ import annotations

from typing import Literal

from langchain.agents import create_agent

from agent.src.prompts import SYSTEM_PROMPT, output_directive
from agent.src.tools import (
    GROUNDING_RECORDER,
    RETRIEVAL_RECORDER,
    RETRIEVAL_STATE,
    RetrievedSource,
    retrieve,
)
from llm import get_chat_model, guard_input, guard_output, usage_callbacks


Mode = Literal["short", "memo", "annotate"]


def build_agent():
    """Construct a LangGraph ReAct-style agent with the retrieve tool.

    The LLM comes from `llm.get_chat_model()`, which resolves the active
    model profile (LAWAGENT_PROFILE / config/profiles.yaml). Do not
    instantiate models directly in this file.
    """
    return create_agent(
        model=get_chat_model(),
        tools=[retrieve],
        system_prompt=SYSTEM_PROMPT,
    )


def ask_with_sources(
    question: str, mode: Mode = "short", state: str | None = None
) -> tuple[str, list[RetrievedSource]]:
    """Run the agent and return the answer plus the chunks it retrieved.

    Sources are captured from inside the `retrieve` tool via a
    ContextVar, so they reflect what the agent actually pulled — not
    whatever URLs the LLM remembered or invented.

    `state` selects the jurisdiction's vector collection (a slug like "ny");
    `None` retrieves from Connecticut. The caller sets it — not the LLM.
    """
    # Bedrock guardrail on the *question* first: catch prompt-injection /
    # off-scope asks before we spend a model call. No-op unless a guardrail
    # is configured (LAWAGENT_BEDROCK_GUARDRAIL_ID).
    gin = guard_input(question)
    if gin.blocked:
        return gin.text, []

    agent = build_agent()
    user_message = f"{output_directive(mode)}\n\nQuestion: {question}"

    sources: list[RetrievedSource] = []
    grounding: list[str] = []
    token = RETRIEVAL_RECORDER.set(sources)
    grounding_token = GROUNDING_RECORDER.set(grounding)
    state_token = RETRIEVAL_STATE.set(state)
    try:
        # `usage_callbacks()` meters token usage into the active recorder
        # (llm.usage.record_usage), set by the API's /chat handler. It's a
        # no-op when no recorder is active (CLI runs).
        result = agent.invoke(
            {"messages": [("user", user_message)]},
            config={"callbacks": usage_callbacks()},
        )
    finally:
        RETRIEVAL_RECORDER.reset(token)
        GROUNDING_RECORDER.reset(grounding_token)
        RETRIEVAL_STATE.reset(state_token)

    final = result["messages"][-1]
    answer = final.content if hasattr(final, "content") else str(final)

    # Bedrock contextual-grounding guardrail: verify the answer traces to the
    # passages actually retrieved (the anti-hallucination check), and mask any
    # PII. `gout.text` is the answer unchanged, a PII-masked version, or a
    # refusal. No-op unless a guardrail is configured.
    gout = guard_output(question, answer, "\n\n---\n\n".join(grounding))
    answer = gout.text

    # Dedupe (citation, url) while keeping the agent's retrieval order.
    seen: set[tuple[str, str]] = set()
    uniq: list[RetrievedSource] = []
    for s in sources:
        key = (s["citation"], s.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)

    return answer, uniq


def ask(question: str, mode: Mode = "short", state: str | None = None) -> str:
    """Run the agent and return just the final answer text.

    Kept as a thin wrapper over `ask_with_sources` so existing string-only
    callers (CLI, programmatic entrypoint) keep working unchanged.
    """
    answer, _ = ask_with_sources(question, mode=mode, state=state)
    return answer
