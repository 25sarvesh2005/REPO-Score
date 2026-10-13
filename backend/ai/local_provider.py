"""
Local Ollama and vLLM AI Provider Implementation.
Adheres strictly to AI_ARCHITECTURE.md, ADR-005, AI-004, and AI-008.
Default, free-first, privacy-preserving local execution with zero third-party cloud egress.
"""

import json
import time
from typing import Any

import httpx
from pydantic import ValidationError

from backend.ai.models import AIAnalysisPayload, AIAnalysisResult
from backend.ai.provider import IAIProvider


class LocalProvider(IAIProvider):
    """
    Self-hosted local inference provider communicating with Ollama REST API.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "llama3.2:3b",
        temperature: float = 0.1,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._temperature = temperature

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def generate_analysis(
        self,
        prompt: str,
        system_instruction: str,
        timeout_seconds: int = 60,
    ) -> AIAnalysisResult:
        t0 = time.monotonic()
        url = f"{self._base_url}/api/generate"

        payload: dict[str, Any] = {
            "model": self._model_name,
            "prompt": prompt,
            "system": system_instruction,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": self._temperature,
                "num_predict": 2048,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            duration_ms = int((time.monotonic() - t0) * 1000)
            raw_response_text = data.get("response", "").strip()

            # Parse JSON and validate against strict canonical Pydantic schema (AI-006)
            parsed_json = json.loads(raw_response_text)
            validated_payload = AIAnalysisPayload.model_validate(parsed_json)

            prompt_tokens = data.get("prompt_eval_count")
            completion_tokens = data.get("eval_count")
            tokens_total = (prompt_tokens or 0) + (completion_tokens or 0) or None

            return AIAnalysisResult(
                payload=validated_payload,
                provider=self.provider_name,
                model_name=self.model_name,
                prompt_version="1.0.0",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                tokens_consumed=tokens_total,
                duration_ms=duration_ms,
                success=True,
                error_message=None,
                is_fallback=False,
            )

        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return AIAnalysisResult(
                payload=AIAnalysisPayload(
                    executive_summary="Ollama daemon is currently offline or unreachable.",
                    architectural_assessment="Local AI analysis unavailable.",
                ),
                provider=self.provider_name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                success=False,
                error_message=f"Connection to local Ollama server failed: {exc}",
                is_fallback=True,
            )
        except httpx.TimeoutException as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return AIAnalysisResult(
                payload=AIAnalysisPayload(
                    executive_summary="AI inference timed out.",
                    architectural_assessment="Local AI analysis timed out.",
                ),
                provider=self.provider_name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                success=False,
                error_message=f"Inference request exceeded timeout of {timeout_seconds}s: {exc}",
                is_fallback=True,
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return AIAnalysisResult(
                payload=AIAnalysisPayload(
                    executive_summary="Invalid JSON structure received from model.",
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
                    executive_summary="Unexpected error during inference.",
                    architectural_assessment="Analysis incomplete.",
                ),
                provider=self.provider_name,
                model_name=self.model_name,
                duration_ms=duration_ms,
                success=False,
                error_message=f"Unexpected error during local AI inference: {exc}",
                is_fallback=True,
            )
