"""Score the adversarial contribution that GitHub-Metrics leaves unset.

Reads per-repository documents produced by GitHub-Metrics and writes a
releasable pass/fail summary alongside a detailed report carrying the
adversarial country breakdown.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("siat-foreign-analysis")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
