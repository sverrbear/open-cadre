"""LLM provider layer — unified interface to 100+ providers via LiteLLM."""

from cadre.providers.base import LLMProvider
from cadre.providers.litellm_provider import LiteLLMProvider
from cadre.providers.registry import ModelCatalog, ProviderRegistry

__all__ = ["LLMProvider", "LiteLLMProvider", "ModelCatalog", "ProviderRegistry"]
