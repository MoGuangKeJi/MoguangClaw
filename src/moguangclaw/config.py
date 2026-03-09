from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import shutil
from typing import Any

import yaml


_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass(slots=True)
class LLMProviderConfig:
    model: str
    api_key: str
    base_url: str
    temperature: float = 0.2
    max_tokens: int = 4000


@dataclass(slots=True)
class BashToolConfig:
    timeout: int = 30
    confirm_mode: str = "never"
    deny_patterns: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FileToolConfig:
    allowed_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ToolsConfig:
    bash: BashToolConfig = field(default_factory=BashToolConfig)
    file: FileToolConfig = field(default_factory=FileToolConfig)


@dataclass(slots=True)
class MemoryConfig:
    max_history_turns: int = 12


@dataclass(slots=True)
class AgentConfig:
    max_turns: int = 20


@dataclass(slots=True)
class AppConfig:
    default_provider: str
    workspace_root: Path
    llm: dict[str, LLMProviderConfig]
    tools: ToolsConfig
    memory: MemoryConfig
    agent: AgentConfig
    config_path: Path

    def provider_config(self, name: str | None = None) -> LLMProviderConfig:
        provider_name = name or self.default_provider
        if provider_name not in self.llm:
            raise KeyError(f"Unknown LLM provider: {provider_name}")
        return self.llm[provider_name]


def _deep_expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_expand_env(item) for item in value]
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda m: os.getenv(m.group(1), ""), value)
    return value


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _template_workspace_dir() -> Path:
    return _repo_root() / "workspace"


def initialize_workspace(workspace_root: Path, template_workspace: Path | None = None) -> None:
    template_dir = template_workspace or _template_workspace_dir()
    workspace_root = workspace_root.expanduser().resolve()

    if not template_dir.exists():
        workspace_root.mkdir(parents=True, exist_ok=True)
        return

    if not workspace_root.exists():
        workspace_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(template_dir, workspace_root)
        return

    for item in template_dir.iterdir():
        target = workspace_root / item.name
        if target.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def load_config(config_path: str | Path = "config.yaml", init_workspace: bool = True) -> AppConfig:
    config_file = Path(config_path).expanduser().resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")

    raw_data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    data = _deep_expand_env(raw_data)

    default_provider = data.get("default_provider", "qianwen")
    workspace_root = Path(data.get("workspace_root", "~/.moguangclaw/workspace")).expanduser().resolve()

    llm_data: dict[str, Any] = data.get("llm", {})
    llm_config: dict[str, LLMProviderConfig] = {}
    for name, cfg in llm_data.items():
        llm_config[name] = LLMProviderConfig(
            model=cfg.get("model", ""),
            api_key=cfg.get("api_key", ""),
            base_url=cfg.get("base_url", ""),
            temperature=float(cfg.get("temperature", 0.2)),
            max_tokens=int(cfg.get("max_tokens", 4000)),
        )

    tools_data = data.get("tools", {})
    bash_data = tools_data.get("bash", {})
    file_data = tools_data.get("file", {})

    tools = ToolsConfig(
        bash=BashToolConfig(
            timeout=int(bash_data.get("timeout", 30)),
            confirm_mode=str(bash_data.get("confirm_mode", "never")),
            deny_patterns=list(bash_data.get("deny_patterns", [])),
        ),
        file=FileToolConfig(
            allowed_paths=list(file_data.get("allowed_paths", [])),
        ),
    )

    memory = MemoryConfig(max_history_turns=int(data.get("memory", {}).get("max_history_turns", 12)))
    agent = AgentConfig(max_turns=int(data.get("agent", {}).get("max_turns", 20)))

    config = AppConfig(
        default_provider=default_provider,
        workspace_root=workspace_root,
        llm=llm_config,
        tools=tools,
        memory=memory,
        agent=agent,
        config_path=config_file,
    )

    if init_workspace:
        initialize_workspace(workspace_root)

    return config
