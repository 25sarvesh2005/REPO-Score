# Phase 02 Report — Threat Model & Sandbox Security Specification

> **Phase:** 02  
> **Phase Name:** Threat Model and Sandbox Security Specification  
> **Status:** PASS  
> **Target System:** RepoScore — Autonomous Repository Intelligence & Software Evaluation Engine  
> **Governance Authority:** `phases/02_SECURITY.md`, `phases/00_ARCHITECTURE.md`, `AGENTS.md`

---

## 1. Executive Summary

Phase 02 establishes the formal security architecture, hostile repository threat model, container sandbox confinement specification, prompt injection defense framework, and security verification test plan for **RepoScore**.

In strict adherence to the Prime Directives and Phase 02 rules:
- **No production code** was implemented.
- **Evidence Over Assumption** is strictly preserved.
- **Hostile Code Threat Model** is fully formalized: all untrusted repository code is quarantined within hardened Docker sandboxes; execution on the host is strictly prohibited.
- **Docker is NOT described as perfect isolation:** Residual risks (kernel zero-days, CPU side channels, LLM jailbreaks) are explicitly documented, and future microVM isolation paths (`ISandboxManager`) are formalized.
- **Deterministic Core Scoring** remains protected behind an architectural firewall where AI models have zero scoring authority.
- **All threats and mitigations are testable**, accompanied by an explicit 24-test security verification matrix.

---

## 2. Start State & Pre-Phase Audit

- **Starting Git Commit:** `9d12c49` (`docs(plan): establish phase execution contracts 02-18 and CI backtracking guidelines`)
- **Last Known-Good Phase Commit:** `2b25d7e` (`phase(01): establish software requirements`)
  - *Evidence:* [`docs/phase-reports/PHASE_01.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/phase-reports/PHASE_01.md) (Status: **PASS**), 11 requirements documents, 197 formal requirements validated and committed.
- **ADRs Audited:** ADR-001 through ADR-010 verified intact; [ADR-002 (Docker Sandbox Architecture)](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/architecture/adrs/ADR-002_DOCKER_SANDBOX_ARCHITECTURE.md) is the binding architectural decision governing this phase.
- **Git History & State Verified:** Clean working tree, zero uncommitted modifications, zero regressions identified.

---

## 3. Deliverables Created & Modified

### Deliverables Created under `docs/security/`:
1. [`docs/security/THREAT_MODEL.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/security/THREAT_MODEL.md) — Comprehensive STRIDE attack surface analysis, trust boundaries diagram, 9 in-depth threat vectors (TV-01 through TV-09), detailed mitigations, and explicit residual risks.
2. [`docs/security/SANDBOX_SECURITY_SPEC.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/security/SANDBOX_SECURITY_SPEC.md) — Complete technical hardening specification: non-root UID 10001 / GID 10001, `--cap-drop=ALL`, `no-new-privileges:true`, Seccomp syscall filter, read-only rootfs with bounded tmpfs, cgroups v2 quotas (2GB RAM, 2 CPU cores, 128 PIDs), phased network egress proxy and `--network none`, secret isolation, and teardown invariants.
3. [`docs/security/PROMPT_INJECTION_DEFENSE.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/security/PROMPT_INJECTION_DEFENSE.md) — Prompt injection threat analysis (direct and indirect), tamper-evident `<UNTRUSTED_REPOSITORY_DATA>` boundary delimiter architecture, system prompt hardening, temperature $0.1$ inference parameters, Pydantic structured output validation, and the deterministic scoring firewall.
4. [`docs/security/SECURITY_TEST_PLAN.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/security/SECURITY_TEST_PLAN.md) — Automated verification matrix mapping 24 security test cases (SEC-TEST-01 to SEC-TEST-24) to threat vectors, components, and phases, with 5 standardized adversarial test fixture specifications (`fork_bomb_repo`, `oom_memory_repo`, `zip_slip_archive`, `ssrf_metadata_repo`, `prompt_injection_repo`).
5. [`docs/phase-reports/PHASE_02.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/docs/phase-reports/PHASE_02.md) — This Phase 02 completion report.

---

## 4. Threat Model & Confinement Summary

### 4.1 Primary Security Controls
- **Host / Sandbox Barrier:** Zero execution of untrusted code on the host OS. All builds, dependency installs, application boots, and test runs execute inside Docker containers.
- **Least Privilege:** UID 10001 (`sandbox`), GID 10001. All 38 Linux capabilities dropped (`--cap-drop=ALL`).
- **Syscall Lockdown:** Custom Seccomp profile denying dangerous syscalls (`ptrace`, `sys_chroot`, `mount`, `bpf`, `keyctl`, `kexec_load`).
- **Filesystem Security:** Read-only rootfs (`--read-only`), read-only snapshot mount (`/workspace/src:ro`), bounded tmpfs scratchpads (`/workspace/build` 1024MB, `/tmp` 256MB with `nodev,nosuid`).
- **Resource Denial-of-Service Defense:** cgroups v2 memory limit 2048MB (swap disabled, OOM killer enabled), CPU limit 2.0 cores, PID limit 128 (neutralizing fork bombs), stdout/stderr stream truncated at 10MB per step.
- **Network Egress Phasing:**
  - Build Phase: Egress permitted only via internal proxy with strict domain whitelisting (`pypi.org`, `registry.npmjs.org`); private IP ranges, cloud metadata (`169.254.169.254`), and host ports are dropped.
  - Runtime Phase: Absolute network severance (`--network none`).
- **Secret Zero-Leakage:** Environment variable whitelisting ensures host credentials never enter containers; automated regex log redaction masks API keys and tokens.
- **Prompt Injection Defense:** Untrusted repository text enclosed in `<UNTRUSTED_REPOSITORY_DATA>` tags; system prompt instructs model to ignore directives in data; Pydantic schema validation rejects malformed responses; AI models have zero authority over numerical scores.

### 4.2 Explicit Residual Risks
1. **Linux Kernel Zero-Day Escapes:** Container isolation does not protect against unpatched host kernel vulnerabilities. Non-root execution and capability stripping minimize attack surface; Phase 17 will introduce microVM isolation (Firecracker) for hardware virtualization.
2. **CPU Hardware Side Channels:** Speculative execution vulnerabilities (Spectre/Meltdown) on shared physical cores.
3. **Advanced LLM Jailbreaks:** Adversarial prompt encoding could influence qualitative text summaries, but deterministic numerical scores remain 100% uncorrupted.

---

## 5. Architectural Integrity & Regression Audit

- [x] Confirmed zero architectural drift from Phase 00 architecture documents and ADRs.
- [x] Docker is explicitly acknowledged as defense-in-depth, NOT an absolute security boundary.
- [x] AI role boundary remains strictly advisory; zero AI scoring authority.
- [x] Untrusted repository code remains 100% sandboxed.
- [x] No production implementation was introduced.

---

## 6. Acceptance Criteria Checklist

- [x] Threats and mitigations are testable (24 test cases defined in `SECURITY_TEST_PLAN.md`).
- [x] Residual risks are explicitly documented (Section 5 of `THREAT_MODEL.md`).
- [x] Docker is NOT described as perfect isolation (Defense-in-depth and kernel limitations explicit).
- [x] Previous-phase regression audit completed and documented (Phase 00 & Phase 01 intact).
- [x] Security verification test matrix and fixtures defined.
- [x] No architecture drift without an ADR.
- [x] `docs/phase-reports/PHASE_02.md` created with required metadata.
- [x] Working tree and diff reviewed before commit.

---

## 7. Commit Information

- **Required Commit Message:** `phase(02): define security threat model`
- **Commit SHA:** `PENDING_COMMIT` *(Will be populated immediately post-commit)*

---

## 8. Handoff to Phase 03

**Next Phase:** **Phase 03 — Data Model and Persistence Design** ([`phases/03_DATA_MODEL.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/phases/03_DATA_MODEL.md))

Phase 03 must:
1. Review [`AGENTS.md`](file:///c:/Partition/SERIOUS%20PROJECTS/REPO-Score/AGENTS.md), Phase 00 architecture, Phase 01 requirements, Phase 02 security specs, and Phase 01/02 reports.
2. Design the PostgreSQL relational data model, table schemas, foreign key cascade behaviors, indexes, and JSONB schemas.
3. Establish data immutability triggers for finalized evaluations, audit trails, and snapshot representations.
