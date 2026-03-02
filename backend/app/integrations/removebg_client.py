"""Remove.bg API client for background removal."""

import httpx

from app.config import settings

REMOVEBG_API_URL = "https://api.remove.bg/v1.0/removebg"


class RemoveBgClient:
    """Remove background from images using Remove.bg API."""

    def __init__(self) -> None:
        self._api_key = settings.removebg_api_key

    async def remove_background(self, image_data: bytes) -> bytes:
        """Send image to Remove.bg and return the processed image bytes."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                REMOVEBG_API_URL,
                headers={"X-Api-Key": self._api_key},
                files={"image_file": ("image.png", image_data, "image/png")},
                data={"size": "auto", "format": "png"},
            )
            response.raise_for_status()
            return response.content

    async def remove_background_from_url(self, image_url: str) -> bytes:
        """Remove background from an image URL."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                REMOVEBG_API_URL,
                headers={"X-Api-Key": self._api_key},
                data={"image_url": image_url, "size": "auto", "format": "png"},
            )
            response.raise_for_status()
            return response.content


_removebg_instance: RemoveBgClient | None = None


def get_removebg_client() -> RemoveBgClient:
    """Singleton accessor."""
    global _removebg_instance
    if _removebg_instance is None:
        _removebg_instance = RemoveBgClient()
    return _removebg_instance
