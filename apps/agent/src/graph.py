from __future__ import annotations

from typing import Literal

from langgraph.prebuilt import create_react_agent

from agent.src.prompts import SYSTEM_PROMPT, output_directive
from agent.src.tools import retrieve
from llm import get_chat_model


Mode = Literal["short", "memo", "annotate"]


def build_agent():
    """Construct a LangGraph ReAct-style agent with the retrieve tool.

    The LLM comes from `llm.get_chat_model()` — change provider/model
    via env vars or by passing args there. Do not instantiate models
    directly in this file.
    """
    return create_react_agent(
        model=get_chat_model(),
        tools=[retrieve],
        prompt=SYSTEM_PROMPT,
    )


def ask(question: str, mode: Mode = "short") -> str:
    """Run the agent on a question and return the final answer text."""
    agent = build_agent()
    user_message = f"{output_directive(mode)}\n\nQuestion: {question}"
    result = agent.invoke({"messages": [("user", user_message)]})
    final = result["messages"][-1]
    return final.content if hasattr(final, "content") else str(final)
