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

# Function to seed database if empty
seed_if_empty() {
    echo "🌱 Checking if database needs seeding..."

    # Set PYTHONPATH to include the app directory
    export PYTHONPATH=/app:$PYTHONPATH

    # Create temporary file for count
    COUNT_FILE=$(mktemp)

    # Check if database has any AI models (write to file to avoid stdout contamination)
    python3 << 'PYTHON_SCRIPT' > "$COUNT_FILE" 2>/dev/null
import asyncio
import sys
import os

# Suppress all logging before imports
os.environ['SQLALCHEMY_SILENCE_UBER_WARNING'] = '1'
os.environ['PYTHONWARNINGS'] = 'ignore'

import logging
logging.disable(logging.CRITICAL)

from sqlalchemy import select, func
from app.infrastructure.database.connection import AsyncSessionLocal
from app.infrastructure.database.models import AIModelORM

async def check_models():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(AIModelORM))
        count = result.scalar()
        return count

try:
    count = asyncio.run(check_models())
    print(count)
    sys.exit(0)
except Exception:
    print(0)
    sys.exit(1)
PYTHON_SCRIPT

    MODEL_COUNT=$(cat "$COUNT_FILE" | tr -d ' \n\r')
    rm -f "$COUNT_FILE"

    # Default to 0 if empty
    MODEL_COUNT=${MODEL_COUNT:-0}

    if [ "$MODEL_COUNT" = "0" ]; then
        echo "🌱 Database is empty, running seed script..."
        python3 -m app.infrastructure.database.seed

        if [ $? -eq 0 ]; then
            echo "✅ Database seeded successfully!"
        else
            echo "⚠️  Seed script failed, but continuing..."
        fi
    else
        echo "✅ Database already has $MODEL_COUNT AI models, skipping seed"
    fi
}

# Main execution
wait_for_postgres
run_migrations
seed_if_empty

echo "🎯 Starting FastAPI application..."
echo ""

# Execute the CMD from Dockerfile (passed as arguments to this script)
exec "$@"
