from __future__ import annotations

from typing import Optional

from ..config import AppConfig
from .base import BaseLLMProvider
from .openai_provider import OpenAIProvider
from .qianwen import QianwenProvider


def create_provider(config: AppConfig, provider_name: Optional[str] = None) -> BaseLLMProvider:
    selected = provider_name or config.default_provider
    provider_cfg = config.provider_config(selected)

    if selected == "qianwen":
        return QianwenProvider(
            model=provider_cfg.model,
            api_key=provider_cfg.api_key,
            base_url=provider_cfg.base_url,
            temperature=provider_cfg.temperature,
            max_tokens=provider_cfg.max_tokens,
        )

    if selected == "openai":
        return OpenAIProvider(
            model=provider_cfg.model,
            api_key=provider_cfg.api_key,
            base_url=provider_cfg.base_url,
            temperature=provider_cfg.temperature,
            max_tokens=provider_cfg.max_tokens,
        )

    raise ValueError(f"Unsupported provider: {selected}")


__all__ = ["BaseLLMProvider", "OpenAIProvider", "QianwenProvider", "create_provider"]
