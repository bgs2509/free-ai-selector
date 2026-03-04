"""Фикстуры для тестов Telegram Bot."""
import os

# КРИТИЧНО: установить env ДО импорта app.main (Bot() требует токен)
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF-fake-token")
os.environ.setdefault("BUSINESS_API_URL", "http://test-business:8000")
