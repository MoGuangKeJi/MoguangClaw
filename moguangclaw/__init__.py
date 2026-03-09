"""Bootstrap package so src-layout works without PYTHONPATH tweaks."""

from __future__ import annotations

from pathlib import Path
import pkgutil

__path__ = pkgutil.extend_path(__path__, __name__)  # type: ignore[name-defined]
_src_pkg = Path(__file__).resolve().parent.parent / "src" / "moguangclaw"
if _src_pkg.exists():
    __path__.append(str(_src_pkg))  # type: ignore[attr-defined]

from .config import AppConfig, load_config

__all__ = ["AppConfig", "load_config"]
