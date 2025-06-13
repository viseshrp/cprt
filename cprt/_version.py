"""The version module for the cprt package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cprt")
except PackageNotFoundError:  # pragma: no cover
    # Fallback for local dev or editable installs
    __version__ = "0.0.0"
