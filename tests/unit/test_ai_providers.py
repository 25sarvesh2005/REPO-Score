"""
Unit tests for AI providers (LocalProvider, ExternalProvider).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.ai.external_provider import ExternalProvider
from backend.ai.local_provider import LocalProvider


@pytest.mark.asyncio
async def test_local_provider_successful_inference():
    provider = LocalProvider(base_url="http://localhost:11434", model_name="llama3.2:3b")

    mock_ollama_resp = {
        "response": json.dumps(
            {
                "executive_summary": "High quality codebase.",
                "architectural_assessment": "Clean modular architecture.",
                "security_risk_narrative": "No critical vulnerabilities.",
                "top_strengths": ["Strong tests"],
                "critical_risks": [],
                "recommendations": [],
            }
        ),
        "prompt_eval_count": 200,
        "eval_count": 100,
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_ollama_resp
    mock_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate_analysis("prompt", "system")

        assert result.success is True
        assert result.provider == "ollama"
        assert result.payload.executive_summary == "High quality codebase."
        assert result.tokens_consumed == 300


@pytest.mark.asyncio
async def test_local_provider_connection_failure():
    provider = LocalProvider(base_url="http://localhost:11434")

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        result = await provider.generate_analysis("prompt", "system")

        assert result.success is False
        assert result.is_fallback is True
        assert "Connection to local Ollama server failed" in result.error_message


@pytest.mark.asyncio
async def test_local_provider_schema_validation_error():
    provider = LocalProvider(base_url="http://localhost:11434")

    # Malformed JSON response
    mock_ollama_resp = {"response": "This is raw unstructured text not JSON"}
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_ollama_resp
    mock_response.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        result = await provider.generate_analysis("prompt", "system")

        assert result.success is False
        assert result.is_fallback is True
        assert "schema validation failed" in result.error_message.lower()


@pytest.mark.asyncio
async def test_external_provider_unavailable_without_key():
    provider = ExternalProvider(api_key=None)
    assert await provider.is_available() is False

    result = await provider.generate_analysis("prompt", "system")
    assert result.success is False
    assert result.is_fallback is True
    assert "API key missing" in result.error_message
