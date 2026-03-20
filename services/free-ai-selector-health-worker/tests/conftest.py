"""Фикстуры для тестов Health Worker."""
import os

os.environ.setdefault("DATA_API_URL", "http://test-data-api:8001")
os.environ.setdefault("BUSINESS_API_URL", "http://test-business-api:8000")
os.environ.setdefault("AUDIT_ENABLED", "false")
