# Out-of-Scope Specification (OOS)

> **Document:** `OUT_OF_SCOPE.md`  
> **System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Status:** Active / Requirements Baseline  
> **Phase:** Phase 01 — Requirements Engineering  
> **Authority:** `phases/01_REQUIREMENTS.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Purpose of Boundary Enforcement

To maintain engineering velocity, architectural integrity, and uncompromising security, this document explicitly declares capabilities, integrations, and operational models that are **strictly OUT OF SCOPE** for RepoScore during early implementation phases (Phases 01 through 13).

Engineers and autonomous agents MUST NOT implement, prototype, or introduce dependencies supporting any capability listed herein without an approved Architecture Decision Record (ADR) and explicit phase scope expansion.

---

## 2. Explicit Out-of-Scope Classifications

### 2.1 Execution & Infrastructure Boundaries
1. **Direct Host Execution:**
   - Under no circumstances will untrusted repository code, build scripts, or binaries execute directly on the host operating system. All execution is quarantined in sandboxes.
2. **Production Cloud Deployment of Evaluated Code:**
   - RepoScore evaluates software; it does not deploy, host, or run customer applications in production. Deployments to AWS ECS, Google Cloud Run, Azure App Services, or Kubernetes clusters are strictly out of scope.
3. **Unrestricted Internet Access from Sandboxes:**
   - Sandbox environments will never receive unrestricted outbound internet access. Package downloads are proxied through an internal caching proxy during builds, and all network connectivity is severed (`--network none`) during runtime evaluation.
4. **Autonomous Code Modification / Committing:**
   - RepoScore is an intelligence and evaluation platform. It does NOT automatically push Git commits, open Pull Requests, or mutate code in upstream repositories.
5. **MicroVM Hardware Virtualization (in MVP):**
   - While the architecture abstracts isolation behind `ISandboxManager`, hardware-level virtualization runtimes (AWS Firecracker microVMs, Kata Containers) are out of scope for MVP and scheduled for Phase 17 (Hardening). Standard hardened Docker/runc isolation is used initially.

### 2.2 Language & Technology Support Boundaries
6. **Exotic & Compiled Systems Languages (in MVP):**
   - Full runtime compilation and execution of C, C++, Rust, Go, Java, Swift, Kotlin, Haskell, and Scala are out of scope for the MVP. (Basic static language detection is permitted, but runtime sandboxed build/probe will initially support Python and Node.js only).
7. **Multi-Service & Monorepo Distributed Orchestration:**
   - Evaluating multi-tier monorepos requiring complex inter-service orchestration (e.g. Docker Compose setups with 5 interconnected microservices and Kafka clusters) is out of scope for early phases. The MVP targets standalone or single-tier services.
8. **Mobile & Desktop GUI Applications:**
   - Compiling, launching, or testing native Android (APK), iOS (IPA), Electron, Flutter, or desktop GUI applications is strictly out of scope.

### 2.3 Commercial, Multi-Tenant & Enterprise Features
9. **Enterprise Single Sign-On (SSO):**
   - Integrations with SAML 2.0, Okta, Microsoft Entra ID (Azure AD), and LDAP are out of scope for the initial release.
10. **Billing, Metering & Payment Gateways:**
    - Subscription billing, stripe payment gateways, usage metering, and invoice generation are strictly excluded.
11. **Plugin Marketplace:**
    - Third-party app stores, dynamic untrusted plugin loading, and external community extensions are prohibited.
12. **Multi-Node Kubernetes Worker Fleets:**
    - High-density distributed Kubernetes worker clusters using KEDA or complex autoscalers are deferred. The initial release deploys via Docker Compose with local worker processes.

### 2.4 AI Model Boundaries
13. **Mandatory Paid Cloud AI Services:**
    - Proprietary cloud LLM APIs (OpenAI GPT-4, Anthropic Claude) MUST NOT be required for core platform functionality. The system must run completely self-hosted using local Ollama models.
14. **Autonomous Agentic Coding Loops:**
    - Allowing LLMs to write code and execute iterative trial-and-error shell commands on the host is strictly prohibited.

---

## 3. Scope Modification Protocol

If an implementation agent or collaborator encounters a requirement that appears to conflict with this Out-of-Scope specification:
1. **HALT work immediately.**
2. Do not silently implement the excluded feature.
3. Submit a formal Architecture Decision Record (ADR) update request.
4. Obtain explicit human user approval before introducing any previously excluded capabilities.
