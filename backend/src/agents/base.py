"""Blindspot — Base Agent Class (Google GenAI)

All agents inherit from BaseAgent which provides:
- Shared state access
- Google Gemini API via new google.genai package
- Output validation against Pydantic schemas
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from google import genai
from google.genai import types as genai_types
from src.config import settings
from src.state.schema import BlindspotState


class BaseAgent(ABC):
    """Base class for all Blindspot agents."""

    name: str = "base"
    description: str = "Base agent"
    model_preference: str = "pro"  # "pro" or "flash"

    def __init__(self):
        self.state: Optional[BlindspotState] = None
        self._client = None

        if settings.google_api_key and settings.llm_enabled:
            self._client = genai.Client(api_key=settings.google_api_key)

    @property
    def client(self):
        """Public alias for the Gemini client."""
        return self._client

    def set_state(self, state: BlindspotState):
        """Inject shared state into agent."""
        self.state = state

    def call_llm(self, prompt: str, system: str = "", temperature: float = 0.1) -> str:
        """Call Gemini API using new google.genai package, with cache fallback."""
        
        # Generate cache key
        from src.cache.cache_layer import global_cache
        cache_inputs = {"agent": self.name, "prompt": prompt, "system": system}
        cache_key = global_cache.get_cache_key(cache_inputs)

        # Check cache if demo mode is enabled or if LLM is disabled
        if settings.demo_mode or not settings.llm_enabled:
            cached = global_cache.get_cached_response(cache_key)
            if cached is not None:
                return cached
            if not settings.llm_enabled:
                raise RuntimeError(f"Live LLM disabled and no cache hit for {self.name}")

        if not settings.google_api_key or not settings.llm_enabled:
            raise ValueError("Live LLM disabled or Google API key not configured")

        if not self._client:
            raise ValueError("Gemini client not initialized")

        try:
            # Select model based on agent preference
            if self.model_preference == "flash":
                model_name = settings.gemini_flash_model
            else:
                model_name = settings.gemini_pro_model

            # Build content with system instruction
            if system:
                full_prompt = f"{system}\n\n{prompt}"
            else:
                full_prompt = prompt

            response = self._client.models.generate_content(
                model=model_name,
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=settings.max_tokens,
                ),
            )

            result_text = None
            if response.text:
                result_text = response.text
            else:
                parts = []
                for candidate in response.candidates or []:
                    content = getattr(candidate, "content", None)
                    for part in getattr(content, "parts", []) or []:
                        text = getattr(part, "text", "")
                        if text:
                            parts.append(text)
                if parts:
                    result_text = "\n".join(parts)

            if result_text:
                # Save to cache on successful call
                global_cache.set_cached_response(cache_key, result_text, prefix=self.name)
                return result_text

            finish_reasons = [
                str(getattr(candidate, "finish_reason", "unknown"))
                for candidate in response.candidates or []
            ]
            raise RuntimeError(f"Gemini returned no text. Finish reasons: {finish_reasons}")

        except Exception as e:
            # Fallback to cache on error
            cached = global_cache.get_cached_response(cache_key)
            if cached is not None:
                return cached
            raise RuntimeError(f"Gemini API call failed for {self.name} and no cache hit: {str(e)}")

    @abstractmethod
    def run(self) -> Dict[str, Any]:
        """Execute agent logic. Returns state mutation dict."""
        pass

    def validate_output(self, output: Dict[str, Any], schema_cls: type) -> Any:
        """Validate output against Pydantic schema."""
        return schema_cls(**output)
