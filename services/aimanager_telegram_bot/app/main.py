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
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "aimanager_telegram_bot"
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
        logger.error(f"Business API call failed: {str(e)}")
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
        logger.error(f"Failed to fetch models stats: {str(e)}")
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
• Используйте /help для получения справки

<b>Провайдеры:</b>
✅ HuggingFace
✅ Replicate
✅ Together.ai

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

<b>Как работает бот:</b>
1️⃣ Вы отправляете текстовый запрос
2️⃣ Бот автоматически выбирает лучшую AI модель на основе надёжности
3️⃣ Запрос обрабатывается выбранной моделью
4️⃣ Вы получаете ответ с информацией об использованной модели

<b>Формула надёжности:</b>
reliability_score = (success_rate × 0.6) + (speed_score × 0.4)

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
        logger.error(f"Business API connection failed: {str(e)}")
        logger.warning("Bot will start but may encounter errors")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info(f"Shutting down {SERVICE_NAME}")


if __name__ == "__main__":
    asyncio.run(main())
