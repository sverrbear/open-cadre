"""Error classification — user-friendly messages for LLM API errors."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CadreError:
    """Classified error with user-friendly message and recovery hint."""

    category: str  # auth, rate_limit, connection, bad_request, unknown
    message: str
    hint: str
    original: Exception | None = field(default=None, repr=False)


def classify_llm_error(error: Exception) -> CadreError:
    """Classify a LiteLLM/API exception into a user-friendly CadreError."""
    error_str = str(error).lower()

    # Try litellm-specific exception types first
    type_name = type(error).__name__

    if type_name == "AuthenticationError" or "authentication" in error_str:
        provider = _extract_provider(error_str)
        hint = f"Run `cadre keys set {provider}` to configure your API key"
        return CadreError(
            category="auth",
            message=f"Authentication failed for {provider}",
            hint=hint,
            original=error,
        )

    if type_name == "RateLimitError" or "rate_limit" in error_str or "rate limit" in error_str:
        return CadreError(
            category="rate_limit",
            message="Rate limit exceeded",
            hint="Wait a moment and try again, or switch to a different model",
            original=error,
        )

    if (
        type_name in ("APIConnectionError", "Timeout", "APITimeoutError")
        or "timeout" in error_str
        or "connection" in error_str
    ):
        return CadreError(
            category="connection",
            message="Could not connect to the API",
            hint="Check your internet connection. If using Ollama, ensure it's running.",
            original=error,
        )

    if type_name == "BadRequestError" or "bad request" in error_str:
        return CadreError(
            category="bad_request",
            message="Invalid request to the API",
            hint="Check the model name with `cadre models list`",
            original=error,
        )

    if type_name == "NotFoundError" or "not found" in error_str:
        return CadreError(
            category="bad_request",
            message="Model or endpoint not found",
            hint="Check the model name with `cadre models list`",
            original=error,
        )

    return CadreError(
        category="unknown",
        message=f"Unexpected error: {type_name}",
        hint="Run `cadre doctor` to check your setup",
        original=error,
    )


def format_error_for_display(error: CadreError) -> str:
    """Format a CadreError for display in chat pane. Returns plain string."""
    return f"{error.message}\n  Hint: {error.hint}"


def _extract_provider(error_str: str) -> str:
    """Try to extract a provider name from an error string."""
    for name in ("anthropic", "openai", "google", "mistral", "ollama"):
        if name in error_str:
            return name
    return "your provider"
