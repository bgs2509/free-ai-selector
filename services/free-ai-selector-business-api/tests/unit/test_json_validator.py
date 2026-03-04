"""Тесты для app/utils/json_validator.py."""
import pytest

from app.utils.json_validator import validate_json_response


class TestValidateJsonResponse:
    """Тесты для validate_json_response."""

    def test_valid_json_direct(self):
        """Прямой валидный JSON парсится без изменений."""
        result = validate_json_response('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_valid_json_with_whitespace(self):
        """JSON с пробелами по краям обрезается."""
        result = validate_json_response('  {"key": "value"}  ')
        assert result == '{"key": "value"}'

    def test_markdown_json_block(self):
        """JSON извлекается из markdown-блока с меткой json."""
        text = '```json\n{"key": "value"}\n```'
        result = validate_json_response(text)
        assert result == '{"key": "value"}'

    def test_markdown_block_without_json_label(self):
        """JSON извлекается из markdown-блока без метки json."""
        text = '```\n{"key": "value"}\n```'
        result = validate_json_response(text)
        assert result == '{"key": "value"}'

    def test_json_embedded_in_text(self):
        """JSON-объект извлекается из текста с обрамлением."""
        text = 'Here is the result: {"answer": 42} hope this helps'
        result = validate_json_response(text)
        assert '"answer": 42' in result

    def test_invalid_json_raises(self):
        """Невалидный текст без JSON вызывает ValueError."""
        with pytest.raises(ValueError, match="not valid JSON"):
            validate_json_response("this is not json at all")

    def test_empty_string_raises(self):
        """Пустая строка вызывает ValueError."""
        with pytest.raises(ValueError):
            validate_json_response("")

    def test_nested_json(self):
        """Вложенный JSON парсится корректно."""
        text = '{"outer": {"inner": "value"}}'
        result = validate_json_response(text)
        assert '"inner"' in result

    def test_json_array_direct(self):
        """Прямой JSON-массив парсится корректно."""
        result = validate_json_response('[1, 2, 3]')
        assert result == '[1, 2, 3]'

    def test_markdown_block_with_extra_text(self):
        """JSON из markdown-блока среди прочего текста."""
        text = 'Some preamble text\n```json\n{"result": true}\n```\nSome trailing text'
        result = validate_json_response(text)
        assert result == '{"result": true}'

    def test_multiple_json_objects_returns_first(self):
        """При нескольких JSON-объектах возвращается первый найденный."""
        text = 'first: {"a": 1} second: {"b": 2}'
        result = validate_json_response(text)
        # re.DOTALL с жадным .* захватит максимальный объект
        assert '"a": 1' in result

    def test_only_whitespace_raises(self):
        """Строка из пробелов вызывает ValueError."""
        with pytest.raises(ValueError):
            validate_json_response("   ")

    def test_broken_json_in_markdown_falls_through(self):
        """Невалидный JSON в markdown-блоке не принимается, ищется далее."""
        text = '```json\n{broken json\n```\n{"fallback": true}'
        result = validate_json_response(text)
        assert '"fallback"' in result
