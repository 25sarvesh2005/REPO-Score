# ADR-005: Local-First AI Architecture

> **Status:** Accepted  
> **Date:** 2026-10-08  
> **Deciders:** AI Systems Architecture Team  
> **Consulted:** Core Architecture & DevOps Team  

---

## Context
RepoScore leverages AI to synthesize human-readable summaries, diagnose root causes of runtime crashes, and provide remediation guidance. However, relying exclusively on paid, proprietary cloud LLM APIs (such as OpenAI, Anthropic, or Gemini) creates significant problems:
1. Operational costs scale linearly with evaluation volume.
2. Users and enterprises often cannot transmit proprietary repository code to external third-party cloud LLMs.
3. Network outages, rate limits, or API deprecations can stall system operation.

---

## Decision
We adopt a **Local-First AI Architecture**:
- The default, first-class AI provider is a locally-hosted open-weights model running via **Ollama** or **vLLM** (e.g. `llama3.2:3b`, `mistral:7b`, `qwen2.5-coder:7b`).
- AI inference runs within the self-hosted environment, ensuring zero external data transmission and zero token subscription fees.
- The subsystem is architected behind an abstract `IAIProvider` interface:
  - `LocalProvider` (Default, self-hosted Ollama)
  - `ExternalProvider` (Optional fallback for users who explicitly provide cloud API keys)
- If the AI provider is offline or times out, the evaluation completes successfully with full deterministic scoring and structured evidence intact.

---

## Alternatives Considered
1. **Cloud-Only Proprietary APIs (OpenAI/Anthropic Exclusive)**:
   - *Rejected*: Incur continuous operational billing; impossible to run offline in air-gapped or privacy-conscious environments.
2. **No AI Layer (Pure Rule-Based Text Formatting)**:
   - *Rejected*: Lacks narrative synthesis and cannot contextualize complex multi-file architectural antipatterns for human readers.

---

## Consequences
- **Positive**:
  - Completely free to develop, test, and self-host.
  - Zero privacy leakage: Proprietary code never leaves the local host or enterprise boundary.
  - Fully offline and air-gapped capable.
- **Negative**:
  - Local model execution requires sufficient host RAM/VRAM (minimum 8GB system RAM for 3B/7B quantized models).

---

## Security Impact
- Ensures sensitive proprietary repository files and intellectual property remain strictly within the user's infrastructure.

---

## Operational Impact
- Development environment is self-contained: single `ollama run` command or Docker service satisfies all AI prerequisites.
