"""Single source of truth for LLM, embeddings, and model-profile config.

Which models the app uses is defined in `config/profiles.yaml` and
selected with `LAWAGENT_PROFILE`. To switch models, change that env var
(or add a profile to the YAML). Nothing in `apps/` should construct
chat/embeddings models or pick a collection name directly — always go
through this package.
"""

from llm.chat import build_chat_model, get_chat_model
from llm.embeddings import build_embeddings, get_embeddings
from llm.pricing import cost_usd
from llm.profiles import (
    Profile,
    active_collection,
    active_profile_name,
    collection_for,
    get_active_profile,
    load_profiles,
)
from llm.usage import (
    UsageEvent,
    record_embedding,
    record_usage,
    usage_callbacks,
)

__all__ = [
    "get_chat_model",
    "build_chat_model",
    "get_embeddings",
    "build_embeddings",
    "Profile",
    "get_active_profile",
    "active_profile_name",
    "active_collection",
    "collection_for",
    "load_profiles",
    "cost_usd",
    "UsageEvent",
    "record_usage",
    "record_embedding",
    "usage_callbacks",
]
