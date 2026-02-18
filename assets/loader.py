"""Asset loading utilities using importlib.resources."""

from importlib.resources import as_file, files
from pathlib import Path
from typing import Iterator

# Reference to the assets package
_ASSETS = files("assets")


def get_asset_path(filename: str) -> Path:
    """
    Get the path to an asset file.

    Note: For temporary access, use open_asset() instead as this may
    return a temporary path for zipped packages.

    Args:
        filename: Name of the asset file (e.g., "oe_dictionary.csv")

    Returns:
        Path to the asset file
    """
    return Path(str(_ASSETS.joinpath(filename)))


def open_asset(filename: str, mode: str = "r") -> Iterator:
    """
    Open an asset file as a context manager.

    Args:
        filename: Name of the asset file
        mode: File open mode (default "r" for text)

    Yields:
        Open file handle

    Example:
        with open_asset("oe_dictionary.csv") as f:
            reader = csv.reader(f)
            ...
    """
    return _ASSETS.joinpath(filename).open(mode)


def read_asset_text(filename: str) -> str:
    """
    Read an asset file as text.

    Args:
        filename: Name of the asset file

    Returns:
        Contents of the file as a string
    """
    return _ASSETS.joinpath(filename).read_text()


def read_asset_bytes(filename: str) -> bytes:
    """
    Read an asset file as bytes.

    Args:
        filename: Name of the asset file

    Returns:
        Contents of the file as bytes
    """
    return _ASSETS.joinpath(filename).read_bytes()
