"""coqui-ai-api: a REST API wrapper around the Coqui-AI TTS engine.

The version is read from installed package metadata so ``pyproject.toml`` stays
the single source of truth: nothing else in the repository restates it.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

try:
    __version__ = _package_version("coqui-ai-api")
except PackageNotFoundError:  # pragma: no cover - only hit when not installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
