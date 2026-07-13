"""Shared pytest fixtures for MatchAudit tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def fixtures_dir() -> Generator[Path, None, None]:
    """Provide the path to the test fixtures directory."""
    yield Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def sample_csv(fixtures_dir: Path) -> Path:
    """Provide the path to the sample CSV fixture."""
    return fixtures_dir / "sample.csv"


@pytest.fixture
def sample_xlsx(fixtures_dir: Path) -> Path:
    """Provide the path to the sample Excel fixture."""
    return fixtures_dir / "sample.xlsx"


@pytest.fixture
def misaligned_csv(fixtures_dir: Path) -> Path:
    """Provide the path to the misaligned CSV fixture."""
    return fixtures_dir / "misaligned.csv"
