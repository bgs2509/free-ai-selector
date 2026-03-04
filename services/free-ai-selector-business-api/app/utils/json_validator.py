"""Валидация JSON-ответов от AI провайдеров."""

import json
import re


def validate_json_response(text: str) -> str:
    """
    Валидировать и извлечь JSON из ответа провайдера.

    Стратегия:
    1. Попробовать json.loads(text) напрямую
    2. Извлечь из markdown-блока ```json ... ```
    3. Найти первый JSON-объект { ... } в тексте

    Returns:
        Валидная JSON-строка

    Raises:
        ValueError: Если JSON невалиден
    """
    # 1. Прямой парсинг
    try:
        json.loads(text)
        return text.strip()
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Извлечение из markdown ```json ... ```
    md_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if md_match:
        candidate = md_match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Найти первый { ... } объект
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, TypeError):
            pass

    raise ValueError(f"Response is not valid JSON (length={len(text)})")
