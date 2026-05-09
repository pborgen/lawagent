"""lawagent CLI.

Examples:
    python -m cli.main ask "What factors does CGS 46b-82 require?"
    python -m cli.main memo "Pendente lite alimony for a 12-year marriage"
    python -m cli.main annotate "CGS 46b-82"
"""
from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown


app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _run(question: str, mode: str) -> None:
    load_dotenv()
    from agent.src.graph import ask  # local import: faster CLI startup

    console.print(f"[dim]mode:[/dim] {mode}")
    console.print(f"[bold]Q:[/bold] {question}\n")
    answer = ask(question, mode=mode)  # type: ignore[arg-type]
    console.print(Markdown(answer))


@app.command()
def ask(question: str) -> None:
    """Short answer with citations."""
    _run(question, mode="short")


@app.command()
def memo(question: str) -> None:
    """Issue / Rule / Analysis / Conclusion memo with citations."""
    _run(question, mode="memo")


@app.command()
def annotate(target: str) -> None:
    """Show a statute or rule with the agent's annotations."""
    _run(target, mode="annotate")


if __name__ == "__main__":
    app()
