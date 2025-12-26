#!/bin/bash

# Deployment script for VPS
# This script stops containers, pulls latest changes, and rebuilds production containers

set -e  # Exit on any error

echo "================================================"
echo "🚀 Starting deployment process..."
echo "================================================"

# Создание внешней сети proxy-network (для связи с nginx-proxy)
# Если сеть уже существует — команда завершится успешно без ошибки
echo ""
echo "🌐 Проверка/создание внешней сети proxy-network..."
docker network create proxy-network 2>/dev/null && echo "   Сеть proxy-network создана" || echo "   Сеть proxy-network уже существует"

# Stop and remove existing containers
echo ""
echo "🛑 Stopping existing containers..."
docker compose down

# Pull latest changes from git
echo ""
echo "📥 Pulling latest changes from git..."
sudo GIT_SSH_COMMAND='ssh -i /home/bgs/.ssh/HenryBud_Ubuntu_Lenovo73 -o IdentitiesOnly=yes' git pull

# Build and start production containers
echo ""
echo "🔨 Building and starting production containers..."
docker compose --env-file .env up --build -d

echo ""
echo "================================================"
echo "✅ DOCKER SYSTEM PRUNE -FORCE!"
echo "================================================"
docker system prune --force


echo ""
echo "================================================"
echo "✅ Deployment completed successfully!"
echo "================================================"
echo ""
echo "📊 ALL Container status:"
docker ps
