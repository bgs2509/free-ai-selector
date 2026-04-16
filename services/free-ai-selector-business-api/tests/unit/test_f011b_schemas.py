"""
Unit tests for F011-B: System Prompts & JSON Response schemas
"""

import pytest
from pydantic import ValidationError

from app.api.v1.schemas import ProcessPromptRequest
from app.domain.models import PromptRequest


@pytest.mark.unit
class TestProcessPromptRequestSchema:
    """Test ProcessPromptRequest schema validation (F011-B)."""

    def test_minimal_request_without_optional_fields(self):
        """Test that request works without optional F011-B fields."""
        request = ProcessPromptRequest(prompt="Test prompt")

        assert request.prompt == "Test prompt"
        assert request.system_prompt is None  # F011-B optional
        assert request.response_format is None  # F011-B optional

    def test_request_with_system_prompt(self):
        """Test request with system_prompt field (F011-B)."""
        request = ProcessPromptRequest(
            prompt="Test prompt", system_prompt="You are a helpful assistant."
        )

        assert request.prompt == "Test prompt"
        assert request.system_prompt == "You are a helpful assistant."
        assert request.response_format is None

    def test_request_with_response_format(self):
        """Test request with response_format field (F011-B)."""
        request = ProcessPromptRequest(prompt="Test prompt", response_format={"type": "json_object"})

        assert request.prompt == "Test prompt"
        assert request.system_prompt is None
        assert request.response_format == {"type": "json_object"}

    def test_request_with_model_name(self):
        """Test request with model_name field (F019)."""
        request = ProcessPromptRequest(prompt="Test prompt", model_name="Llama 3.1 8B")

        assert request.prompt == "Test prompt"
        assert request.model_name == "Llama 3.1 8B"

    def test_model_name_must_be_non_empty(self):
        """Test that model_name must be non-empty string (F019)."""
        with pytest.raises(ValidationError):
            ProcessPromptRequest(prompt="Test prompt", model_name="")

    def test_request_with_both_optional_fields(self):
        """Test request with both system_prompt and response_format (F011-B)."""
        request = ProcessPromptRequest(
            prompt="Test prompt",
            system_prompt="You are a JSON assistant.",
            response_format={"type": "json_object"},
        )

        assert request.prompt == "Test prompt"
        assert request.system_prompt == "You are a JSON assistant."
        assert request.response_format == {"type": "json_object"}

    def test_system_prompt_max_length_validation(self):
        """Test that system_prompt respects max_length constraint (F011-B)."""
        # 5000 characters should pass
        long_system_prompt = "A" * 5000
        request = ProcessPromptRequest(prompt="Test", system_prompt=long_system_prompt)
        assert len(request.system_prompt) == 5000

        # 5001 characters should fail
        too_long_system_prompt = "A" * 5001
        with pytest.raises(ValidationError) as exc_info:
            ProcessPromptRequest(prompt="Test", system_prompt=too_long_system_prompt)

        errors = exc_info.value.errors()
        assert any(
            "system_prompt" in str(error["loc"]) and "at most 5000 characters" in str(error["msg"])
            for error in errors
        )

    def test_response_format_rejects_json_schema(self):
        """Test response_format rejects json_schema type (only json_object allowed)."""
        schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "test_schema",
                "schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
            },
        }

        with pytest.raises(ValidationError) as exc_info:
            ProcessPromptRequest(prompt="Test prompt", response_format=schema)

        errors = exc_info.value.errors()
        assert any("response_format" in str(error["loc"]) for error in errors)

    def test_response_format_rejects_invalid_type(self):
        """Test response_format rejects unknown type values."""
        with pytest.raises(ValidationError):
            ProcessPromptRequest(prompt="Test prompt", response_format={"type": "invalid"})

        with pytest.raises(ValidationError):
            ProcessPromptRequest(prompt="Test prompt", response_format={"foo": "bar"})


@pytest.mark.unit
class TestPromptRequestDTO:
    """Test PromptRequest DTO (F011-B)."""

    def test_dto_without_optional_fields(self):
        """Test DTO creation without optional F011-B fields."""
        dto = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        assert dto.user_id == "test_user"
        assert dto.prompt_text == "Test prompt"
        assert dto.system_prompt is None  # F011-B optional
        assert dto.response_format is None  # F011-B optional

    def test_dto_with_system_prompt(self):
        """Test DTO with system_prompt field (F011-B)."""
        dto = PromptRequest(
            user_id="test_user", prompt_text="Test prompt", system_prompt="You are helpful."
        )

        assert dto.user_id == "test_user"
        assert dto.prompt_text == "Test prompt"
        assert dto.system_prompt == "You are helpful."
        assert dto.response_format is None

    def test_dto_with_model_name(self):
        """Test DTO with model_name field (F019)."""
        dto = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            model_name="Llama 3.1 8B",
        )

        assert dto.user_id == "test_user"
        assert dto.prompt_text == "Test prompt"
        assert dto.model_name == "Llama 3.1 8B"

    def test_dto_with_response_format(self):
        """Test DTO with response_format field (F011-B)."""
        dto = PromptRequest(
            user_id="test_user", prompt_text="Test prompt", response_format={"type": "json_object"}
        )

        assert dto.user_id == "test_user"
        assert dto.prompt_text == "Test prompt"
        assert dto.system_prompt is None
        assert dto.response_format == {"type": "json_object"}

    def test_dto_with_both_optional_fields(self):
        """Test DTO with both system_prompt and response_format (F011-B)."""
        dto = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            system_prompt="System message",
            response_format={"type": "json_object"},
        )

        assert dto.user_id == "test_user"
        assert dto.prompt_text == "Test prompt"
        assert dto.system_prompt == "System message"
        assert dto.response_format == {"type": "json_object"}


@pytest.mark.unit
class TestTagsParameter:
    """Tests for tags parameter in API schema."""

    def test_schema_accepts_tags(self):
        from app.api.v1.schemas import ProcessPromptRequest

        req = ProcessPromptRequest(prompt="hello", tags=["fast", "json"])
        assert req.tags == ["fast", "json"]

    def test_schema_tags_optional(self):
        from app.api.v1.schemas import ProcessPromptRequest

        req = ProcessPromptRequest(prompt="hello")
        assert req.tags is None

    def test_domain_prompt_request_tags(self):
        from app.domain.models import PromptRequest

        req = PromptRequest(user_id="u1", prompt_text="hello", tags=["code"])
        assert req.tags == ["code"]
