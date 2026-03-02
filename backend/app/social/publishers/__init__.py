"""Social media publisher factory."""

from app.social.publishers.instagram import InstagramPublisher
from app.social.publishers.tiktok import TikTokPublisher


def get_publisher(platform: str):
    """Return the publisher for a given platform."""
    if platform == "instagram":
        return InstagramPublisher()
    elif platform == "tiktok":
        return TikTokPublisher()
    raise ValueError(f"Unknown social platform: {platform}")
