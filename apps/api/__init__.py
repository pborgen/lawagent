"""HTTP API for the lawagent assistant.

Thin FastAPI layer so the Next.js frontend (`apps/web`) can reach the
LangGraph agent and pgvector store. All retrieval and prompting stays
in Python — see `apps/api/main.py`.
"""
