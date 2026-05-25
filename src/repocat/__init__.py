"""repocat — TODO."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("repocat")
except PackageNotFoundError:
    __version__ = "0.0.0"


def main() -> None:
    print("Hello from repocat!")
