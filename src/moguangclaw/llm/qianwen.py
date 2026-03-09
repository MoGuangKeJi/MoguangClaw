from __future__ import annotations

from typing import Any

from .openai_provider import OpenAIProvider


class QianwenProvider(OpenAIProvider):
    """DashScope Qwen provider via OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature: float = 0.2,
        max_tokens: int = 4000,
        client: Any | None = None,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            client=client,
        )
