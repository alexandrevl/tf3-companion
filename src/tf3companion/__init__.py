"""TF3 Companion package metadata."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("tf3-companion")
except PackageNotFoundError:
    __version__ = "0.1.0"
