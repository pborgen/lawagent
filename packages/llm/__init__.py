"""Single source of truth for LLM and embeddings configuration.

To switch the LLM, change `LAWAGENT_LLM_PROVIDER` / `LAWAGENT_LLM_MODEL`
in your .env (or pass overrides to `get_chat_model`). Nothing in
`apps/` should construct chat models or embeddings directly — always
go through this package.
"""

from llm.chat import get_chat_model
from llm.embeddings import get_embeddings

__all__ = ["get_chat_model", "get_embeddings"]
