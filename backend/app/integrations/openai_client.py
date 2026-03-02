"""OpenAI API client — implements AIProvider Protocol for text + image generation."""

from openai import AsyncOpenAI

from app.config import settings


class OpenAIClient:
    """Wrapper around OpenAI API for GPT-4o-mini and DALL-E 3."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        """Generate text using GPT-4o-mini."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def generate_image(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> bytes:
        """Generate an image using DALL-E 3. Returns image bytes."""
        import httpx

        response = await self._client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=1,
            response_format="url",
        )
        image_url = response.data[0].url
        async with httpx.AsyncClient() as http:
            img_response = await http.get(image_url)
            return img_response.content


_openai_instance: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient:
    """Singleton accessor."""
    global _openai_instance
    if _openai_instance is None:
        _openai_instance = OpenAIClient()
    return _openai_instance
