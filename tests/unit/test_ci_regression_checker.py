"""
Unit tests for Commit-Aware Regression Checker (Phase 15).
"""

from unittest.mock import patch, MagicMock
import pytest

from scripts.ci_regression_checker import (
    map_files_to_test_targets,
    sanitize_text,
    SUBSYSTEM_TEST_MAP,
)


def test_map_files_to_test_targets_sandbox():
    """Verify sandbox modifications map to sandbox focused test suite."""
    files = ["backend/sandbox/manager.py", "backend/sandbox/models.py"]
    targets, subsystems = map_files_to_test_targets(files)

    assert "backend/sandbox" in subsystems
    assert "tests/unit/test_sandbox_validator.py" in targets
    assert "tests/adversarial/test_adversarial_sandbox.py" in targets


def test_map_files_to_test_targets_scoring():
    """Verify scoring modifications map to scoring tests and adversarial pipeline tests."""
    files = ["backend/scoring/calculator.py"]
    targets, subsystems = map_files_to_test_targets(files)

    assert "backend/scoring" in subsystems
    assert "tests/unit/test_scoring_calculator.py" in targets
    assert "tests/adversarial/test_adversarial_pipeline.py" in targets


def test_map_files_to_direct_test_files():
    """Verify modifying a test directly maps that test target."""
    files = ["tests/unit/test_queue.py"]
    targets, subsystems = map_files_to_test_targets(files)

    assert "tests/unit/test_queue.py" in targets
    assert len(subsystems) == 0


def test_map_files_docs_no_subsystems():
    """Verify modifying docs files does not trigger false positive subsystem targets."""
    files = ["docs/architecture/SYSTEM_ARCHITECTURE.md", "README.md"]
    targets, subsystems = map_files_to_test_targets(files)

    assert len(targets) == 0
    assert len(subsystems) == 0


def test_sanitize_text_redactions():
    """Verify sensitive tokens and connection strings are cleanly redacted."""
    raw = (
        "Found token ghp_1234567890abcdef1234567890abcdef1234\n"
        "Found aws key AKIAIOSFODNN7EXAMPLE\n"
        "Connect to postgresql://admin:supersecret@localhost:5432/db\n"
        "Clean message text."
    )
    clean = sanitize_text(raw)

    assert "[REDACTED_GH_TOKEN]" in clean
    assert "ghp_1234567890abcdef" not in clean
    assert "[REDACTED_AWS_KEY]" in clean
    assert "AKIAIOSFODNN7EXAMPLE" not in clean
    assert "supersecret" not in clean
    assert "postgresql://[REDACTED_USER]:[REDACTED_PASS]@localhost:5432/db" in clean
    assert "Clean message text." in clean
