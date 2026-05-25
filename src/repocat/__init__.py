"""Repository capture CLI package."""

from importlib.metadata import PackageNotFoundError, version

from repocat.cli import app

try:
    __version__ = version("repocat")
except PackageNotFoundError:
    __version__ = "0.0.0"


def main() -> None:
    """Run the repocat command-line application."""
    app()
