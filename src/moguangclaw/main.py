from __future__ import annotations

import argparse
import asyncio

from .agent.context import ContextBuilder
from .agent.loop import AgentLoop
from .agent.runner import AgentRunner
from .channels.cli import CLIChannel
from .config import load_config
from .llm import create_provider
from .memory.store import SessionStore
from .tools.registry import build_default_registry


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MoguangClaw CLI entrypoint")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--provider", default=None, help="Override provider name")
    parser.add_argument("--session-id", default="cli-default", help="Session id")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    return parser


async def _run(args: argparse.Namespace) -> None:
    config = load_config(args.config, init_workspace=True)
    provider = create_provider(config, args.provider)

    tool_registry = build_default_registry(config)
    tool_registry.export_tools_markdown(config.workspace_root / "TOOLS.md")

    session_store = SessionStore(
        sessions_dir=config.workspace_root / "sessions",
        max_history_turns=config.memory.max_history_turns,
    )
    context_builder = ContextBuilder(
        workspace_root=config.workspace_root,
        max_history_turns=config.memory.max_history_turns,
    )

    agent_loop = AgentLoop(
        provider=provider,
        tool_registry=tool_registry,
        session_store=session_store,
        context_builder=context_builder,
        max_turns=config.agent.max_turns,
    )
    runner = AgentRunner(loop=agent_loop)

    channel = CLIChannel(session_id=args.session_id, stream=not args.no_stream)
    await channel.run(runner)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
