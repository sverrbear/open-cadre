"""Tests for error classification."""

from __future__ import annotations

from cadre.errors import CadreError, classify_llm_error, format_error_for_display


# Create named exception classes to match LiteLLM error type names
class AuthenticationError(Exception):
    pass


class RateLimitError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class BadRequestError(Exception):
    pass


class NotFoundError(Exception):
    pass


def test_classify_auth_error():
    err = AuthenticationError("invalid x-api-key")
    result = classify_llm_error(err)
    assert result.category == "auth"
    assert "API key" in result.hint


def test_classify_auth_from_string():
    """Falls back to string matching when type name doesn't match."""
    err = Exception("authentication failed for anthropic")
    result = classify_llm_error(err)
    assert result.category == "auth"


def test_classify_rate_limit():
    err = RateLimitError("rate limit exceeded")
    result = classify_llm_error(err)
    assert result.category == "rate_limit"


def test_classify_rate_limit_from_string():
    err = Exception("rate_limit exceeded")
    result = classify_llm_error(err)
    assert result.category == "rate_limit"


def test_classify_connection_error():
    err = Exception("connection refused")
    result = classify_llm_error(err)
    assert result.category == "connection"


def test_classify_timeout():
    err = APITimeoutError("request timed out")
    result = classify_llm_error(err)
    assert result.category == "connection"


def test_classify_bad_request():
    err = BadRequestError("model not found")
    result = classify_llm_error(err)
    assert result.category == "bad_request"


def test_classify_not_found():
    err = NotFoundError("not found")
    result = classify_llm_error(err)
    assert result.category == "bad_request"


def test_classify_unknown():
    err = ValueError("something weird")
    result = classify_llm_error(err)
    assert result.category == "unknown"
    assert "ValueError" in result.message


def test_format_error_for_display():
    error = CadreError(
        category="auth",
        message="Authentication failed for anthropic",
        hint="Run `cadre keys set anthropic` to configure your API key",
    )
    output = format_error_for_display(error)
    assert "Authentication failed" in output
    assert "Hint:" in output
    assert "cadre keys set" in output


def test_classify_auth_extracts_provider():
    err = AuthenticationError("anthropic authentication error")
    result = classify_llm_error(err)
    assert "anthropic" in result.hint


def test_classify_model_error():
    """ModelError (validated key, model-specific failure) gives actionable hint."""
    from cadre.providers.litellm_provider import ModelError

    original = Exception("InternalServerError: OpenAIException - Connection error")
    err = ModelError("openai/o3", "openai", original)
    result = classify_llm_error(err)
    assert result.category == "model"
    assert "o3" in result.message
    assert "API key is valid" in result.hint
    assert "fallback" in result.hint.lower()
    assert result.original is original


def test_classify_model_error_does_not_match_regular_errors():
    """Regular exceptions should NOT be classified as ModelError."""
    err = Exception("InternalServerError: Connection error")
    result = classify_llm_error(err)
    assert result.category != "model"
