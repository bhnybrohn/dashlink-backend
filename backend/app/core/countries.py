"""Country-based configuration — currency, payment gateways, and fee rates.

Each supported country defines which payment gateways are available,
what currency sellers use, and the platform fee rate.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CountryConfig:
    """Configuration for a supported country."""

    code: str  # ISO 3166-1 alpha-2 (e.g. "NG")
    name: str
    currency: str  # ISO 4217 (e.g. "NGN")
    currency_symbol: str
    supported_gateways: tuple[str, ...]
    default_gateway: str
    platform_fee_rate: Decimal


COUNTRIES: dict[str, CountryConfig] = {
    "NG": CountryConfig(
        code="NG",
        name="Nigeria",
        currency="NGN",
        currency_symbol="\u20a6",
        supported_gateways=("paystack", "flutterwave"),
        default_gateway="paystack",
        platform_fee_rate=Decimal("0.05"),
    ),
    "GH": CountryConfig(
        code="GH",
        name="Ghana",
        currency="GHS",
        currency_symbol="GH\u20b5",
        supported_gateways=("paystack", "flutterwave"),
        default_gateway="paystack",
        platform_fee_rate=Decimal("0.05"),
    ),
    "GB": CountryConfig(
        code="GB",
        name="United Kingdom",
        currency="GBP",
        currency_symbol="\u00a3",
        supported_gateways=("stripe",),
        default_gateway="stripe",
        platform_fee_rate=Decimal("0.05"),
    ),
}


def get_country(code: str) -> CountryConfig:
    """Return the config for a country code. Raises ValueError if unsupported."""
    code = code.upper()
    if code not in COUNTRIES:
        supported = ", ".join(sorted(COUNTRIES))
        raise ValueError(f"Unsupported country: {code}. Supported: {supported}")
    return COUNTRIES[code]


def get_currency_for_country(code: str) -> str:
    """Return the ISO 4217 currency code for a country (e.g. 'NG' → 'NGN')."""
    return get_country(code).currency


def get_default_gateway(code: str) -> str:
    """Return the default payment gateway for a country."""
    return get_country(code).default_gateway


def is_gateway_supported(country_code: str, gateway: str) -> bool:
    """Check if a payment gateway is supported in a country."""
    return gateway in get_country(country_code).supported_gateways


def list_supported_countries() -> list[CountryConfig]:
    """Return all supported countries."""
    return list(COUNTRIES.values())
