"""Pagination utilities."""

from typing import Any


def paginate(items: list[Any], total: int, offset: int, limit: int) -> dict[str, Any]:
    """Build a standard pagination response dict."""
    return {
        "items": items,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": (offset + limit) < total,
    }
