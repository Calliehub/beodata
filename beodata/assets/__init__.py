"""Static assets for beodata package."""

from beodata.assets.loader import (
    get_asset_path,
    open_asset,
    read_asset_bytes,
    read_asset_text,
)

__all__ = [
    "get_asset_path",
    "open_asset",
    "read_asset_bytes",
    "read_asset_text",
]
