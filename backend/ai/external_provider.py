"""
External Cloud AI Provider Implementation (Optional Fallback).
Adheres strictly to AI_ARCHITECTURE.md, ADR-005, and AI-003.
Used ONLY when the user explicitly provides an external API key.
"""

import json
import os
import time
from typing import Any, Dict, Optional
import httpx
from pydantic import ValidationError

from backend.ai.models import AIAnalysisPayload, AIAnalysisResult
from backend.ai.provider import IAIProvider


class ExternalProvider(IAIProvider):
    """
    Optional external cloud provider using OpenAI-compatible chat completion APIs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.1,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._temperature = temperature

    @property
    def provider_name(self) -> str:
        return "external"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def is_available(self) -> bool:
        """Available only when an API key is explicitly configured."""
        return bool(self._api_key and self._api_key.strip())

    async def generate_analysis(
        self,
        prompt: str,
        system_instruction: str,
        timeout_seconds: int = 60,
    ) -> AIAnalysisResult:
        t0 = time.monotonic()

        if not await self.is_available():
            return AIAnalysisResult(
                payload=AIAnalysisPayload(
                    executive_summary="External AI provider API key is not configured.",
                    architectural_assessment="Analysis skipped.",
                ),
                provider=self.provider_name,
                model_name=self.model_name,
                duration_ms=0,
                success=False,
                error_message="External provider API key missing or blank",
                is_fallback=True,
            )

        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self._temperature,
            "max_tokens": 2048,
        }

        try:
            async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            duration_ms = int((time.monotonic() - t0) * 1000)
            choice = data["choices"][0]["message"]["content"].strip()
            parsed_json = json.loads(choice)
            validated_payload = AIAnalysisPayload.model_validate(parsed_json)

            usage = data.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")

            return AIAnalysisResult(
                payload=validated_payload,
                provider=self.provider_name,
                model_name=self.model_name,
                prompt_version="1.0.0",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tokens_consumed=total_tokens,
                duration_ms=duration_ms,
                success=True,
                error_message=None,
                is_fallback=False,
            )

        except (json.JSONDecodeError, ValidationError) as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return AIAnalysisResult(
                payload=AIAnalysisPayload(
                    executive_summary="Schema validation error on external LLM output.",
                    architectural_assessment="Output schema validation failed.",
                ),
                provider=self.provider_name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                success=False,
                error_message=f"Output schema validation failed (AI-006): {exc}",
                is_fallback=True,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return AIAnalysisResult(
                payload=AIAnalysisPayload(
                    executive_summary="External AI provider call failed.",
                    architectural_assessment="Analysis incomplete.",
                ),
                provider=self.provider_name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                success=False,
                error_message=f"External provider API error: {exc}",
                is_fallback=True,
            )
