"""Slug generator using nanoid — URL-safe, non-sequential, non-guessable."""

import re

from nanoid import generate

# URL-safe alphabet (no ambiguous characters)
_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
_SLUG_LENGTH = 6


def generate_slug(name: str, length: int = _SLUG_LENGTH) -> str:
    """Generate a product slug: sanitized-name-<nanoid>.

    Example: 'Red Lipstick Matte' → 'red-lipstick-matte-a7x3k2'
    """
    # Sanitize the name into a URL-friendly base
    base = name.lower().strip()
    base = re.sub(r"[^\w\s-]", "", base)       # remove non-word chars
    base = re.sub(r"[\s_]+", "-", base)         # spaces/underscores → hyphens
    base = re.sub(r"-+", "-", base)             # collapse multiple hyphens
    base = base.strip("-")

    # Truncate base to keep URLs short
    if len(base) > 40:
        base = base[:40].rstrip("-")

    suffix = generate(_ALPHABET, length)
    return f"{base}-{suffix}" if base else suffix


def generate_store_slug(store_name: str) -> str:
    """Generate a storefront slug: @storename.

    Example: 'Amina Beauty' → 'aminabeauty'
    """
    slug = store_name.lower().strip()
    slug = re.sub(r"[^\w]", "", slug)
    return slug
