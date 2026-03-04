"""Тесты для хэндлеров Telegram Bot."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_message():
    """Мок aiogram Message."""
    msg = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 12345
    msg.from_user.first_name = "TestUser"
    msg.text = "Привет"
    msg.answer = AsyncMock()
    msg.chat = MagicMock()
    msg.chat.id = 67890
    msg.bot = AsyncMock()
    msg.bot.send_chat_action = AsyncMock()
    return msg


class TestCmdStart:
    async def test_start_with_api_available(self, mock_message):
        from app.main import cmd_start

        with patch("app.main.get_models_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = {
                "models": [
                    {"name": "Model1", "provider": "Prov1", "reliability_score": 0.9, "is_active": True},
                ],
                "total_models": 1,
            }
            await cmd_start(mock_message)

        mock_message.answer.assert_called_once()
        call_text = mock_message.answer.call_args[0][0]
        assert "Model1" in call_text or "TestUser" in call_text

    async def test_start_api_unavailable(self, mock_message):
        from app.main import cmd_start

        with patch("app.main.get_models_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = None
            await cmd_start(mock_message)

        mock_message.answer.assert_called_once()


class TestCmdHelp:
    async def test_help_returns_text(self, mock_message):
        from app.main import cmd_help

        await cmd_help(mock_message)
        mock_message.answer.assert_called_once()
        call_text = mock_message.answer.call_args[0][0]
        assert "/help" in call_text or "помощь" in call_text.lower() or "команд" in call_text.lower()


class TestCmdStats:
    async def test_stats_with_models(self, mock_message):
        from app.main import cmd_stats

        with patch("app.main.get_models_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = {
                "models": [
                    {"name": "M1", "provider": "P1", "reliability_score": 0.9, "is_active": True,
                     "success_rate": 0.95, "average_response_time": 1.0, "total_requests": 100},
                ],
                "total_models": 1,
            }
            await cmd_stats(mock_message)

        # cmd_stats вызывает answer дважды: "Загружаю..." и результат
        assert mock_message.answer.call_count == 2

    async def test_stats_api_unavailable(self, mock_message):
        from app.main import cmd_stats

        with patch("app.main.get_models_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = None
            await cmd_stats(mock_message)

        # "Загружаю..." + сообщение об ошибке
        assert mock_message.answer.call_count == 2


class TestCmdTest:
    async def test_test_success(self, mock_message):
        from app.main import cmd_test

        with patch("app.main.test_all_providers", new_callable=AsyncMock) as mock_test:
            mock_test.return_value = {
                "total_providers": 2,
                "successful": 1,
                "failed": 1,
                "results": [
                    {"provider": "P1", "model": "M1", "status": "success", "response_time": 1.0, "error": None},
                    {"provider": "P2", "model": "M2", "status": "error", "response_time": None, "error": "Timeout"},
                ],
            }
            await cmd_test(mock_message)

        # answer вызывается минимум 2 раза: "Тестирую..." + результат
        assert mock_message.answer.call_count >= 2

    async def test_test_api_unavailable(self, mock_message):
        from app.main import cmd_test

        with patch("app.main.test_all_providers", new_callable=AsyncMock) as mock_test:
            mock_test.return_value = None
            await cmd_test(mock_message)

        mock_message.answer.assert_called()


class TestHandleTextMessage:
    async def test_success_response(self, mock_message):
        from app.main import handle_text_message

        mock_message.text = "Hello AI"
        with patch("app.main.call_business_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {
                "response": "Hello human",
                "selected_model": "TestModel",
                "provider": "TestProv",
                "response_time_seconds": 1.5,
            }
            await handle_text_message(mock_message)

        mock_message.answer.assert_called()

    async def test_api_error(self, mock_message):
        from app.main import handle_text_message

        mock_message.text = "Hello AI"
        with patch("app.main.call_business_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = None
            await handle_text_message(mock_message)

        mock_message.answer.assert_called()

    async def test_too_long_prompt(self, mock_message):
        from app.main import handle_text_message

        mock_message.text = "x" * 6000
        await handle_text_message(mock_message)
        mock_message.answer.assert_called()

    async def test_long_response_split(self, mock_message):
        from app.main import handle_text_message

        mock_message.text = "test"
        long_response = "A" * 5000
        with patch("app.main.call_business_api", new_callable=AsyncMock) as mock_api:
            mock_api.return_value = {
                "response": long_response,
                "selected_model": "M1",
                "provider": "P1",
                "response_time_seconds": 1.0,
            }
            await handle_text_message(mock_message)

        # Длинный ответ разбивается на несколько сообщений
        assert mock_message.answer.call_count >= 2
