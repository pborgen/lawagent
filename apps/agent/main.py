"""Programmatic entrypoint for the agent.

Most users go through `apps/cli/main.py` — this file is here so the
agent app is runnable on its own for quick checks.
"""
from __future__ import annotations

from rich.console import Console

from agent.src.graph import ask


def main() -> None:
    console = Console()
    question = "What factors must a Connecticut court consider when awarding alimony under § 46b-82?"
    console.print(f"[bold]Q:[/bold] {question}\n")
    answer = ask(question, mode="short")
    console.print(answer)


if __name__ == "__main__":
    main()
