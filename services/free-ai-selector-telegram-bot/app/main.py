"""
AI Manager Platform - Telegram Bot Service

Telegram bot interface for prompt processing with AI.
Level 2 (Development Ready) maturity.
User interface in Russian.
"""

import asyncio
import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "free-ai-selector-telegram-bot"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BUSINESS_API_URL = os.getenv("BUSINESS_API_URL", "http://localhost:8000")
LOG_LEVEL = os.getenv("TELEGRAM_BOT_LOG_LEVEL", "INFO")
BOT_MAX_MESSAGE_LENGTH = int(os.getenv("BOT_MAX_MESSAGE_LENGTH", "4000"))

# =============================================================================
# Logging Configuration (Level 2: JSON logging)
# =============================================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "'
    + SERVICE_NAME
    + '", "message": "%(message)s"}',
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# =============================================================================
# HTTP Client for Business API
# =============================================================================


async def call_business_api(prompt: str) -> Optional[dict]:
    """
    Call Business API to process prompt.

    Args:
        prompt: User's prompt text

    Returns:
        Response dict with AI-generated text, or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BUSINESS_API_URL}/api/v1/prompts/process",
                json={"prompt": prompt},
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        logger.error(f"Business API call failed: {sanitize_error_message(e)}")
        return None


async def get_models_stats() -> Optional[dict]:
    """
    Get models statistics from Business API.

    Returns:
        Stats dict with models info, or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{BUSINESS_API_URL}/api/v1/models/stats")
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch models stats: {sanitize_error_message(e)}")
        return None


async def test_all_providers() -> Optional[dict]:
    """
    Test all AI providers via Business API.

    Returns:
        Test results dict with provider statuses, or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{BUSINESS_API_URL}/api/v1/providers/test")
            response.raise_for_status()
            return response.json()

    except httpx.HTTPError as e:
        logger.error(f"Failed to test providers: {sanitize_error_message(e)}")
        return None


# =============================================================================
# Bot Setup
# =============================================================================

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()
router = Router()

# =============================================================================
# Command Handlers (Russian UI)
# =============================================================================


@router.message(Command("start"))
async def cmd_start(message: Message):
    """
    Handle /start command.

    Russian: Приветствие и краткая информация о боте.
    """
    welcome_text = """
👋 <b>Добро пожаловать в Free AI Selector!</b>

Я автоматически выбираю лучшую бесплатную AI модель для вашего запроса на основе показателей надёжности в реальном времени.

<b>Как использовать:</b>
• Просто отправьте мне любой текст — я обработаю его через самую надёжную AI модель
• Используйте /stats для просмотра статистики моделей
• Используйте /test для проверки работы всех провайдеров
• Используйте /help для получения справки

<b>6 бесплатных AI провайдеров (без кредитной карты):</b>
✅ Google Gemini - Gemini 2.5 Flash
✅ Groq - Llama 3.3 70B (1,800 токенов/сек)
✅ Cerebras - Llama 3.3 70B (2,500+ токенов/сек)
✅ SambaNova - Meta-Llama-3.3-70B-Instruct
✅ HuggingFace - Meta-Llama-3-8B-Instruct
✅ Cloudflare - Llama 3.3 70B FP8 Fast

Начните прямо сейчас — просто отправьте мне сообщение!
"""
    await message.answer(welcome_text, parse_mode="HTML")
    logger.info(f"User {message.from_user.id} started the bot")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    Handle /help command.

    Russian: Подробная справка о командах и функциях.
    """
    help_text = """
📚 <b>Справка по Free AI Selector</b>

<b>Доступные команды:</b>
/start — Начать работу с ботом
/help — Показать эту справку
/stats — Показать статистику моделей
/test — Проверить работу всех AI провайдеров

<b>Как работает бот:</b>
1️⃣ Вы отправляете текстовый запрос
2️⃣ Бот автоматически выбирает лучшую AI модель на основе надёжности
3️⃣ Запрос обрабатывается выбранной моделью
4️⃣ Вы получаете ответ с информацией об использованной модели

<b>Формула надёжности:</b>
reliability_score = (success_rate × 0.6) + (speed_score × 0.4)

<b>Команда /test:</b>
Отправляет тестовый запрос ко всем 6 провайдерам и показывает:
• ✅ Работающие модели и их время ответа
• ❌ Неработающие модели и причину ошибки
• 📊 Общую статистику и самый быстрый провайдер

<b>Примеры запросов:</b>
• "Напиши короткое стихотворение про AI"
• "Объясни квантовую физику простыми словами"
• "Создай список идей для стартапа"

💡 <b>Совет:</b> Чем конкретнее запрос, тем лучше результат!
"""
    await message.answer(help_text, parse_mode="HTML")
    logger.info(f"User {message.from_user.id} requested help")


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """
    Handle /stats command.

    Russian: Показать статистику AI моделей.
    """
    await message.answer("📊 Загружаю статистику моделей...")

    stats = await get_models_stats()

    if stats is None:
        await message.answer(
            "❌ <b>Ошибка:</b> Не удалось получить статистику. Попробуйте позже.",
            parse_mode="HTML",
        )
        return

    models = stats.get("models", [])
    total = stats.get("total_models", 0)

    if total == 0:
        await message.answer("⚠️ Нет доступных моделей.", parse_mode="HTML")
        return

    # Sort by reliability score
    models.sort(key=lambda m: m.get("reliability_score", 0), reverse=True)

    stats_text = f"📊 <b>Статистика AI моделей</b> ({total} моделей)\n\n"

    for i, model in enumerate(models, 1):
        name = model.get("name", "Unknown")
        provider = model.get("provider", "Unknown")
        reliability = model.get("reliability_score", 0.0)
        is_active = model.get("is_active", False)

        status_icon = "✅" if is_active else "❌"
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "•"

        stats_text += f"{medal} <b>{name}</b>\n"
        stats_text += f"   Провайдер: {provider}\n"
        stats_text += f"   Надёжность: {reliability:.3f} {status_icon}\n\n"

    await message.answer(stats_text, parse_mode="HTML")
    logger.info(f"User {message.from_user.id} requested stats")


@router.message(Command("test"))
async def cmd_test(message: Message):
    """
    Handle /test command.

    Russian: Проверить работу всех AI провайдеров.
    Tests all AI providers and returns response time or error details.
    """
    await message.answer("🧪 <b>Тестирую AI провайдеры...</b>\n\nОтправляю тестовый запрос ко всем моделям. Это может занять 10-30 секунд.", parse_mode="HTML")

    test_results = await test_all_providers()

    if test_results is None:
        await message.answer(
            "❌ <b>Ошибка:</b> Не удалось выполнить тестирование. Попробуйте позже.",
            parse_mode="HTML",
        )
        return

    total = test_results.get("total_providers", 0)
    successful = test_results.get("successful", 0)
    failed = test_results.get("failed", 0)
    results = test_results.get("results", [])

    if total == 0:
        await message.answer("⚠️ Нет зарегистрированных провайдеров.", parse_mode="HTML")
        return

    # Build response message
    test_text = f"🧪 <b>Результаты тестирования AI провайдеров</b>\n\n"

    for result in results:
        provider = result.get("provider", "Unknown")
        model = result.get("model", "Unknown Model")
        status = result.get("status", "unknown")
        response_time = result.get("response_time")
        error = result.get("error")

        if status == "success":
            test_text += f"✅ <b>{provider}</b>\n"
            test_text += f"   Модель: {model}\n"
            test_text += f"   ⚡ Время ответа: <b>{response_time:.2f} сек</b>\n\n"
        else:
            test_text += f"❌ <b>{provider}</b>\n"
            test_text += f"   Модель: {model}\n"
            test_text += f"   ⚠️ Ошибка: <code>{error}</code>\n\n"

    # Add summary
    test_text += f"━━━━━━━━━━━━━━━\n"
    test_text += f"📊 <b>Итого:</b> {successful}/{total} работают ({successful/total*100:.1f}%)\n"

    # Find fastest provider
    successful_results = [r for r in results if r.get("status") == "success"]
    if successful_results:
        fastest = min(successful_results, key=lambda r: r.get("response_time", float("inf")))
        test_text += f"⚡ <b>Самый быстрый:</b> {fastest.get('provider')} ({fastest.get('response_time'):.2f} сек)"

    await message.answer(test_text, parse_mode="HTML")
    logger.info(f"User {message.from_user.id} tested providers: {successful}/{total} successful")


# =============================================================================
# Text Message Handler (Prompt Processing)
# =============================================================================


@router.message(F.text)
async def handle_text_message(message: Message):
    """
    Handle text messages (prompt processing).

    Russian: Обработка пользовательских запросов.
    """
    user_prompt = message.text
    user_id = str(message.from_user.id)

    logger.info(f"Processing prompt from user {user_id}: {user_prompt[:50]}...")

    # Send "typing" action
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Limit prompt length
    if len(user_prompt) > 5000:
        await message.answer(
            "❌ <b>Ошибка:</b> Запрос слишком длинный. Максимум 5000 символов.",
            parse_mode="HTML",
        )
        return

    # Call Business API
    response = await call_business_api(user_prompt)

    if response is None:
        await message.answer(
            "❌ <b>Ошибка:</b> Не удалось обработать запрос. Попробуйте позже или используйте /help.",
            parse_mode="HTML",
        )
        return

    # Extract response data
    ai_response = response.get("response", "")
    model_name = response.get("selected_model", "Unknown")
    provider = response.get("provider", "Unknown")
    response_time = response.get("response_time_seconds", 0.0)

    # Format response message
    response_text = f"{ai_response}\n\n"
    response_text += f"━━━━━━━━━━━━━━━\n"
    response_text += f"🤖 <b>Модель:</b> {model_name}\n"
    response_text += f"🔧 <b>Провайдер:</b> {provider}\n"
    response_text += f"⚡ <b>Время:</b> {float(response_time):.2f} сек"

    # Split long messages if needed
    if len(response_text) > BOT_MAX_MESSAGE_LENGTH:
        # Send AI response separately
        await message.answer(ai_response)
        # Send metadata
        metadata = f"🤖 <b>Модель:</b> {model_name}\n🔧 <b>Провайдер:</b> {provider}\n⚡ <b>Время:</b> {float(response_time):.2f} сек"
        await message.answer(metadata, parse_mode="HTML")
    else:
        await message.answer(response_text, parse_mode="HTML")

    logger.info(
        f"Successfully processed prompt for user {user_id} "
        f"with {model_name} in {float(response_time):.2f}s"
    )


# =============================================================================
# Main Function
# =============================================================================

dp.include_router(router)


async def main():
    """
    Main bot entry point.

    Starts polling and handles graceful shutdown.
    """
    logger.info(f"Starting {SERVICE_NAME}")
    logger.info(f"Business API URL: {BUSINESS_API_URL}")

    # Verify Business API connection
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BUSINESS_API_URL}/health")
            if response.status_code == 200:
                logger.info("Business API connection verified")
            else:
                logger.warning(f"Business API health check returned {response.status_code}")
    except Exception as e:
        logger.error(f"Business API connection failed: {sanitize_error_message(e)}")
        logger.warning("Bot will start but may encounter errors")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info(f"Shutting down {SERVICE_NAME}")


if __name__ == "__main__":
    asyncio.run(main())
