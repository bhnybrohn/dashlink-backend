# DashLink Backend

## Quick Start

```bash
# Copy environment variables
cp .env.example .env

# Start all services (API, PostgreSQL, Redis, Celery)
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# Open API docs
open http://localhost:8000/docs
```

## Development (without Docker)

```bash
# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL and Redis locally (or use Docker for just those)
docker compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v
```

## Project Structure

Module-based (vertical slice) architecture — each domain module is self-contained:

```
app/
├── core/          # Shared: base model, base repo, security, protocols
├── auth/          # Registration, login, JWT, MFA
├── users/         # Profile, addresses, GDPR
├── sellers/       # Seller profile, KYC, subscription
├── products/      # Product CRUD, images, variants (Week 2)
├── studio/        # AI generation: images, titles, captions (Week 6)
├── checkout/      # Stock locking, payment initiation (Week 3)
├── orders/        # Order lifecycle (Week 4)
├── payments/      # Multi-gateway webhooks, payouts (Week 3)
├── notifications/ # Email, SMS, WhatsApp, push (Week 4)
├── analytics/     # Event tracking, dashboards (Phase 3)
└── storefront/    # Public storefront + Flash Pages (Week 7)
```
