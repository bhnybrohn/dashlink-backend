"""Centralized prompt templates for AI generation.

Includes prompt injection sanitization and platform-specific formatting.
"""

import re

# ── Sanitization ──


def sanitize_input(text: str) -> str:
    """Strip potential prompt injection patterns from user inputs."""
    # Remove system prompt override attempts
    patterns = [
        r"(?i)ignore\s+(previous|all|above)\s+instructions?",
        r"(?i)you\s+are\s+now\s+",
        r"(?i)system\s*:",
        r"(?i)assistant\s*:",
        r"(?i)\[INST\]",
        r"(?i)<\|im_start\|>",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    return text.strip()


# ── Title Generation ──

TITLE_SYSTEM = (
    "You are a product title expert for an African social commerce platform. "
    "Generate catchy, SEO-friendly product titles. Return exactly 3 title options, "
    "one per line. Keep each under 80 characters. No numbering or bullets."
)

TITLE_PROMPT = """Generate 3 product title options.
Category: {category}
Keywords: {keywords}
{image_context}
"""

# ── Description Generation ──

DESCRIPTION_SYSTEM = (
    "You are a product copywriter for an African social commerce platform. "
    "Write compelling, SEO-optimized product descriptions. "
    "Include key features, benefits, and a call to action. "
    "Keep it under 300 words. Use short paragraphs."
)

DESCRIPTION_PROMPT = """Write a product description.
Title: {title}
Category: {category}
Tone: {tone}
{image_context}
"""

# ── Caption Generation ──

CAPTION_SYSTEM = (
    "You are a social media expert for African sellers. "
    "Generate engaging captions with relevant hashtags. "
    "Match the platform's style and character limits."
)

_PLATFORM_RULES = {
    "instagram": "Max 2200 chars. Include 15-30 relevant hashtags at the end.",
    "x": "Max 280 chars total including hashtags. Be punchy and concise.",
    "tiktok": "Max 150 chars. Trendy, energetic tone. 3-5 hashtags.",
}

CAPTION_PROMPT = """Generate a social media caption.
Product: {product_name}
Platform: {platform}
Tone: {tone}
Rules: {platform_rules}
"""

# ── Image Generation ──

IMAGE_SYSTEM = (
    "Enhance this product image generation prompt to be specific and detailed "
    "for DALL-E 3. Focus on clean product photography style."
)

IMAGE_PROMPT = """Product photo: {prompt}
Style: {style}
Requirements: Clean white or gradient background, professional lighting,
high-resolution product photography style, centered composition.
"""

# ── Template Helpers ──


def build_title_prompt(
    category: str | None, keywords: list[str], image_url: str | None,
) -> str:
    image_context = f"The product image is available at: {image_url}" if image_url else ""
    return TITLE_PROMPT.format(
        category=sanitize_input(category or "general"),
        keywords=sanitize_input(", ".join(keywords) if keywords else "none"),
        image_context=image_context,
    )


def build_description_prompt(
    title: str, category: str | None, tone: str, image_url: str | None,
) -> str:
    image_context = f"The product image is available at: {image_url}" if image_url else ""
    return DESCRIPTION_PROMPT.format(
        title=sanitize_input(title),
        category=sanitize_input(category or "general"),
        tone=tone,
        image_context=image_context,
    )


def build_caption_prompt(product_name: str, platform: str, tone: str) -> str:
    return CAPTION_PROMPT.format(
        product_name=sanitize_input(product_name),
        platform=platform,
        tone=tone,
        platform_rules=_PLATFORM_RULES.get(platform, ""),
    )


def build_image_prompt(prompt: str, style: str) -> str:
    return IMAGE_PROMPT.format(
        prompt=sanitize_input(prompt),
        style=style,
    )
