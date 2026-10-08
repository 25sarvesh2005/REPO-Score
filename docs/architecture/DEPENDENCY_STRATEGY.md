# External Dependency & Free-First Technology Strategy

> **Document:** `DEPENDENCY_STRATEGY.md`  
> **Status:** Active / Architectural Contract  
> **Owner:** Core Architecture Team  
> **Referenced ADRs:** ADR-001, ADR-005, ADR-006, ADR-007

---

## 1. Free-First Dependency Policy

RepoScore is architected around a strict **free-first, open-source-first, self-hostable philosophy**:
1. **Zero Mandatory Paid Subscriptions**: No core capability may depend upon a proprietary paid cloud API.
2. **Permissive Open-Source Licenses**: Third-party libraries must carry permissive licenses (MIT, Apache 2.0, BSD-3, ISC, or EPL). Viral copyleft (GPL-3.0) is avoided in application code, though standalone GPL tools may run as isolated external CLIs.
3. **Pluggable & Replaceable**: Any external tool (whether Semgrep, Ruff, or Ollama) must sit behind an abstract Python interface, allowing drop-in substitution without rewriting pipeline logic.

---

## 2. Comprehensive Dependency Matrix

| Component | Technology | Category | License | Cost | Security Implications | Failure Behavior | Replacement Strategy |
|---|---|---|---|---|---|---|---|
| **API Server** | FastAPI / Uvicorn | `REQUIRED` | MIT | Free | Well-vetted ASGI web server; minimal attack surface. | API crashes; restart via systemd/docker. | Starlette, Litestar |
| **Data Validation** | Pydantic v2 | `REQUIRED` | MIT | Free | Compiled Rust core; validates untrusted JSON inputs. | Throws 422 Unprocessable Entity. | Marshmallow, msgspec |
| **Relational Database** | PostgreSQL 16 | `REQUIRED` | PostgreSQL | Free | Rock-solid ACID persistence; row-level security. | DB read-only/unreachable; tasks back off. | SQLite (local dev), MySQL |
| **Database Driver** | asyncpg / SQLAlchemy | `REQUIRED` | Apache 2.0 / MIT | Free | Binary protocol connection pool; parameterized queries prevent SQLi. | Connection retry with exponential backoff. | psycopg3 |
| **Task Queue & Broker** | Redis 7 | `REQUIRED` | BSD-3-Clause | Free | In-memory queue & pub/sub broker; authenticated. | Queue down; workers wait and reconnect. | RabbitMQ, Postgres LISTEN/NOTIFY |
| **Container Runtime** | Docker Engine | `REQUIRED` | Apache 2.0 | Free | Orchestrates sandboxed execution; kernel isolation. | Sandbox creation fails; job retryable. | Podman, containerd, gVisor |
| **Docker Python SDK** | docker-py | `REQUIRED` | Apache 2.0 | Free | Communicates with dockerd over local Unix socket. | API exceptions logged; jobs abort. | aiodocker, direct Docker CLI |
| **Git Engine** | Git CLI / Dulwich | `REQUIRED` | GPL-2.0 / Apache 2.0 | Free | Clones remote repositories; executed with timeouts. | Ingestion fails; marked NON_RETRYABLE. | libgit2 (pygit2) |
| **Syntax & AST Analysis** | Tree-sitter | `REQUIRED` | MIT | Free | Fast C-based parser; memory safe bindings. | Syntax parse error; emits warning. | Python `ast`, ANTLR |
| **Security Static Scan** | Semgrep OSS | `REPLACEABLE` | LGPL-2.1 | Free | Rule-based AST scanner; runs with network disabled. | Scan skips; logs warning; zero crash. | Bandit, CodeQL, custom AST rules |
| **Python Linter** | Ruff | `REPLACEABLE` | MIT / Apache 2.0 | Free | Native Rust binary; extremely fast linting. | Linting skipped; score neutral. | Flake8, Black, Pylint |
| **Vulnerability Data** | OSV API / Mirror | `REQUIRED` | Apache 2.0 | Free | Free Open Source Vulnerability database queries. | Fallback to cached local JSON dump. | GitHub Advisory DB, Trivy DB |
| **AI Reasoning** | Ollama (Local LLM) | `REPLACEABLE` | MIT | Free | Self-hosted local inference (Llama, Mistral, Qwen). | Evaluation completes without AI narrative. | vLLM, llama.cpp, OpenAI API |
| **Web Frontend** | Next.js 14+ / TS | `REQUIRED` | MIT | Free | Client-side dashboard and visualization. | UI down; API remains fully functional. | Vite + React, SvelteKit |
| **Test Framework** | Pytest / AnyIO | `DEVELOPMENT_ONLY`| MIT | Free | Automated test suite execution in CI. | CI fails. | Unittest |

---

## 3. Dependency Categorization Definitions

- **`REQUIRED`**: Core system dependency indispensable to baseline operations (e.g., PostgreSQL, Docker, FastAPI).
- **`REPLACEABLE`**: Critical functional component that sits behind an adapter interface and can be substituted with an alternative implementation with zero architectural redesign (e.g., Semgrep replaced by Bandit, or Ollama replaced by vLLM).
- **`OPTIONAL`**: Non-essential feature enhancers (e.g., external OpenAI API fallback provider).
- **`DEVELOPMENT_ONLY`**: Tools utilized solely during testing, linting, packaging, and CI builds (e.g., Pytest, Mypy, Black).

---

## 4. Supply Chain Security Controls

1. **Strict Version Pinning**: All production dependencies in `pyproject.toml` and `package.json` must use exact semantic version pinning (e.g., `fastapi==0.115.0`) accompanied by cryptographic lockfiles (`poetry.lock`, `pnpm-lock.yaml`).
2. **Automated Vulnerability Scanning**: CI workflows run automated vulnerability scans (via OSV and Dependabot) against all project dependencies on every pull request.
3. **Zero Host Execution of Repository Packages**: Dependencies declared by target repositories being analyzed are installed **strictly inside ephemeral sandbox containers**, completely separated from the host Python environment.
