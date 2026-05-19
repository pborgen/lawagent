from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from llm.profiles import ChatConfig, get_active_profile


_LOCAL_DEPS_HINT = (
    "Install local LLM deps: uv sync --group local "
    "(or: pip install 'lawagent-monorepo[local]')"
)


def get_chat_model() -> BaseChatModel:
    """Return the chat model for the active profile.

    Which model this is — provider, name, temperature — is defined in
    `config/profiles.yaml` and selected by `LAWAGENT_PROFILE`. Nothing in
    `apps/` should construct chat models directly; always call this.
    """
    return build_chat_model(get_active_profile().chat)


def build_chat_model(cfg: ChatConfig) -> BaseChatModel:
    """Construct a LangChain chat model from a profile's `ChatConfig`."""
    if cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    if cfg.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=cfg.model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    if cfg.provider == "local":
        return _build_local_model(
            cfg.model, cfg.temperature, cfg.max_tokens, cfg.device
        )

    raise ValueError(f"Unhandled chat provider: {cfg.provider!r}")


@lru_cache(maxsize=2)
def _build_local_model(
    model: str,
    temperature: float,
    max_tokens: int,
    device: str,
) -> BaseChatModel:
    """Build an in-process HuggingFace chat model.

    Runs entirely on this machine — no API key. Cached: loading a multi-
    billion-parameter model into RAM is expensive, and the agent would
    otherwise rebuild it on every request. The agent binds a tool to this
    model, so it must support tool calling. Expect slow responses on CPU.
    """
    try:
        from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline
    except ImportError as exc:
        raise ImportError(_LOCAL_DEPS_HINT) from exc

    # transformers' pipeline wants an int index for cpu/cuda, a string for mps.
    pipeline_device = {"cpu": -1, "cuda": 0}.get(device, device)

    pipeline_kwargs: dict = {"max_new_tokens": max_tokens, "return_full_text": False}
    if temperature and temperature > 0:
        pipeline_kwargs.update({"do_sample": True, "temperature": temperature})
    else:
        pipeline_kwargs["do_sample"] = False

    llm = HuggingFacePipeline.from_model_id(
        model_id=model,
        task="text-generation",
        device=pipeline_device,
        pipeline_kwargs=pipeline_kwargs,
    )
    return ChatHuggingFace(llm=llm)
