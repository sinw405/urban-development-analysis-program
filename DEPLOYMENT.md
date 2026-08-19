# Deployment baseline

Development:

    docker compose -f compose.dev.yml config
    docker compose -f compose.dev.yml build
    docker compose -f compose.dev.yml up -d
    Invoke-RestMethod http://localhost:8000/health
    docker compose -f compose.dev.yml down

Production-like:

    Copy-Item production.env.example .env.production
    # Replace all placeholders in .env.production.
    docker compose --env-file .env.production -f compose.prod.yml config
    docker compose --env-file .env.production -f compose.prod.yml build
    docker compose --env-file .env.production -f compose.prod.yml up -d
    docker compose --env-file .env.production -f compose.prod.yml logs migrate
    docker compose --env-file .env.production -f compose.prod.yml exec backend alembic current
    Invoke-WebRequest http://localhost:8080/healthz
    docker compose --env-file .env.production -f compose.prod.yml down

Migration waits for PostgreSQL health. No seed runs automatically. Production rejects debug, fixture, auto-seed, local database, and placeholder-secret settings. Do not use down -v unless deleting the database volume is intended. No external production target is configured.
