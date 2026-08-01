"""The version has exactly one source of truth: pyproject.toml.

These tests exist because the version previously lived in three places
(``VERSION``, ``pyproject.toml``, and a literal in ``app.py``) and they had
already drifted apart: the OpenAPI spec advertised 0.1.0 while the image
shipped 0.1.1.
"""

import re
from importlib.metadata import version as package_version
from pathlib import Path
from types import ModuleType

import coqui_ai_api

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"

# Deliberately not tomllib: that is 3.11+, and the supported floor is 3.10.
_VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


def _declared_version() -> str:
    match = _VERSION_LINE.search(_PYPROJECT.read_text(encoding="utf-8"))
    assert match is not None, "no version field in pyproject.toml"
    return match.group(1)


def test_package_version_matches_pyproject() -> None:
    assert coqui_ai_api.__version__ == _declared_version()


def test_installed_metadata_matches_pyproject() -> None:
    assert package_version("coqui-ai-api") == _declared_version()


def test_openapi_spec_reports_the_package_version(app: ModuleType) -> None:
    assert app.app.api_doc["info"]["version"] == coqui_ai_api.__version__


def test_no_stray_version_file() -> None:
    """A VERSION file would be a second source of truth by definition."""
    assert not (_PYPROJECT.parent / "VERSION").exists()
