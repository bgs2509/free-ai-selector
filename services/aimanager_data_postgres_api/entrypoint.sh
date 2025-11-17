#!/bin/bash
# =============================================================================
# AI Manager Platform - Data API Service Entrypoint
# =============================================================================
# This script:
# 1. Waits for PostgreSQL to be ready
# 2. Runs database migrations automatically
# 3. Starts the FastAPI application
# =============================================================================

set -e

echo "🚀 Starting Data API Service..."

# Function to wait for PostgreSQL
wait_for_postgres() {
    echo "⏳ Waiting for PostgreSQL to be ready..."

    # Extract connection details from DATABASE_URL
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    DB_HOST="${DATABASE_URL#*@}"
    DB_HOST="${DB_HOST%%:*}"
    DB_PORT="${DATABASE_URL#*:}"
    DB_PORT="${DB_PORT%%/*}"
    DB_PORT="${DB_PORT##*:}"

    # Default values if extraction fails
    DB_HOST="${DB_HOST:-postgres}"
    DB_PORT="${DB_PORT:-5432}"

    echo "   Connecting to: ${DB_HOST}:${DB_PORT}"

    MAX_RETRIES=30
    RETRY_COUNT=0

    # Use Python to check PostgreSQL connection
    until python3 -c "import socket; s = socket.socket(); s.settimeout(2); s.connect(('${DB_HOST}', ${DB_PORT})); s.close()" 2>/dev/null || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "   Attempt ${RETRY_COUNT}/${MAX_RETRIES}..."
        sleep 2
    done

    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "❌ PostgreSQL is not available after ${MAX_RETRIES} attempts"
        exit 1
    fi

    echo "✅ PostgreSQL is ready!"
}

# Function to run migrations
run_migrations() {
    echo "📦 Running database migrations..."

    # Set PYTHONPATH to include the app directory
    export PYTHONPATH=/app:$PYTHONPATH

    # Run Alembic migrations
    alembic upgrade head

    if [ $? -eq 0 ]; then
        echo "✅ Migrations completed successfully!"
    else
        echo "❌ Migration failed!"
        exit 1
    fi
}

# Main execution
wait_for_postgres
run_migrations

echo "🎯 Starting FastAPI application..."
echo ""

# Execute the CMD from Dockerfile (passed as arguments to this script)
exec "$@"
