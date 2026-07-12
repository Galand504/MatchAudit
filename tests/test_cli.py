"""Smoke tests for the MatchAudit CLI."""

from __future__ import annotations

import pytest
from click.testing import CliRunner, Result

from matchaudit.cli import main


class TestMatchAuditCli:
    """Smoke tests verifying the CLI boots and responds."""

    def test_help_displays(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit --help`` exits successfully and shows help text."""
        result: Result = cli_runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "MatchAudit" in result.output

    def test_version_displays(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit --version`` shows the package version."""
        result: Result = cli_runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert result.output.strip()

    def test_validate_command_stubbed(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit validate`` shows a stub message."""
        result: Result = cli_runner.invoke(main, ["validate"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_compare_command_stubbed(self, cli_runner: CliRunner) -> None:
        """Running ``matchaudit compare`` shows a stub message."""
        result: Result = cli_runner.invoke(main, ["compare"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    @pytest.mark.parametrize(
        ("args", "expected_exit"),
        [
            (["nonexistent"], 2),
            (["--unknown-flag"], 2),
        ],
    )
    def test_invalid_args_exit_with_error(
        self, cli_runner: CliRunner, args: list[str], expected_exit: int
    ) -> None:
        """Invalid commands or flags exit with code 2 (Click built-in)."""
        result: Result = cli_runner.invoke(main, args)
        assert result.exit_code == expected_exit
