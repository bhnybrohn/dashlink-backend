"""DashLink FastAPI application factory.

Registers all modules (routers), middleware, and exception handlers.
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)

from app.config import settings
from app.core.exceptions import DashLinkError
from app.core.middleware import dashlink_exception_handler, generic_exception_handler, validation_exception_handler, setup_middleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    # Startup
    yield
    # Shutdown — close pools, cleanup
    from app.redis import pool
    await pool.disconnect()


OPENAPI_TAGS = [
    {"name": "Health", "description": "Service health checks"},
    {"name": "Auth", "description": "Registration, login, JWT tokens, MFA, and OAuth social login (Google, Facebook, Twitter)"},
    {"name": "Users", "description": "User profile management and addresses"},
    {"name": "Seller", "description": "Seller profile, payout settings, subscription tiers, KYC verification, team RBAC, and share links"},
    {"name": "Products", "description": "Product CRUD, status transitions, stock, images, variants, scheduling, and bulk CSV upload"},
    {"name": "Checkout", "description": "Stock locking, checkout initiation, payment gateway routing, and country config"},
    {"name": "Orders", "description": "Order lifecycle — status transitions, tracking, and history"},
    {"name": "Payments", "description": "Payment recording, webhook processing (Stripe, Paystack, Flutterwave), and payouts"},
    {"name": "Notifications", "description": "In-app notifications, email, SMS, WhatsApp, and push via Celery"},
    {"name": "Studio", "description": "AI-powered content generation — titles, descriptions, captions, and background removal"},
    {"name": "Storefront", "description": "Public storefront pages, product listings, and flash/promo pages"},
    {"name": "Reviews", "description": "Product reviews, ratings, and seller rating aggregation"},
    {"name": "Social Media", "description": "Connect Instagram & TikTok accounts, publish product photos, and schedule posts"},
    {"name": "Analytics", "description": "Event tracking, seller dashboard overview, traffic, funnel, and revenue charts"},
    {"name": "Discounts", "description": "Seller discount codes — CRUD and checkout validation"},
    {"name": "Disputes", "description": "Buyer/seller dispute resolution with admin escalation"},
    {"name": "Trust & Fraud", "description": "Seller trust scoring, order risk flagging, and admin review"},
    {"name": "CRM", "description": "Customer relationship management — segments, profiles, and broadcast messaging"},
    {"name": "Admin", "description": "Admin-only operations — KYC review, trust management"},
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "DashLink — Social Commerce API\n\n"
            "A full-featured backend for social commerce sellers across Nigeria, Ghana, and the UK. "
            "Supports multi-currency payments (NGN, GHS, GBP), country-based payment gateway routing "
            "(Paystack, Flutterwave, Stripe), OAuth social login, AI-powered product content generation, "
            "and direct posting to Instagram & TikTok."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    # ── Middleware ──
    setup_middleware(app)

    # ── Exception Handlers ──
    from fastapi.exceptions import RequestValidationError
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DashLinkError, dashlink_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)  # type: ignore[arg-type]

    # ── Module Routers ──
    _register_routers(app)

    # ── Health Check ──
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "service": "dashlink-api"}

    return app


def _register_routers(app: FastAPI) -> None:
    """Register all module routers under the API prefix."""
    from app.auth.router import router as auth_router
    from app.users.router import router as users_router
    from app.sellers.router import router as sellers_router
    from app.products.router import router as products_router
    from app.checkout.router import router as checkout_router
    from app.orders.router import router as orders_router
    from app.payments.router import router as payments_router
    from app.notifications.router import router as notifications_router
    from app.studio.router import router as studio_router
    from app.storefront.router import router as storefront_router
    from app.reviews.router import router as reviews_router
    from app.social.router import router as social_router
    from app.analytics.router import router as analytics_router
    from app.discounts.router import router as discounts_router
    from app.disputes.router import router as disputes_router
    from app.trust.router import router as trust_router
    from app.crm.router import router as crm_router

    prefix = settings.api_v1_prefix

    app.include_router(auth_router, prefix=prefix)
    app.include_router(users_router, prefix=prefix)
    app.include_router(sellers_router, prefix=prefix)
    app.include_router(products_router, prefix=prefix)
    app.include_router(checkout_router, prefix=prefix)
    app.include_router(orders_router, prefix=prefix)
    app.include_router(payments_router, prefix=prefix)
    app.include_router(notifications_router, prefix=prefix)
    app.include_router(studio_router, prefix=prefix)
    app.include_router(storefront_router, prefix=prefix)
    app.include_router(reviews_router, prefix=prefix)
    app.include_router(social_router, prefix=prefix)
    app.include_router(analytics_router, prefix=prefix)
    app.include_router(discounts_router, prefix=prefix)
    app.include_router(disputes_router, prefix=prefix)
    app.include_router(trust_router, prefix=prefix)
    app.include_router(crm_router, prefix=prefix)


app = create_app()
