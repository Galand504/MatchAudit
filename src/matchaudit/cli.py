"""MatchAudit CLI — root command and subcommand stubs."""

import click


@click.group()
@click.version_option()
def main() -> None:
    """MatchAudit: data validation and reconciliation for audit teams."""


@main.command()
def validate() -> None:
    """Validate a control point against source data."""
    click.echo("validate: not yet implemented")


@main.command()
def compare() -> None:
    """Compare two datasets and report differences."""
    click.echo("compare: not yet implemented")


if __name__ == "__main__":
    main()
