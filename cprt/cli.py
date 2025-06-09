from __future__ import annotations

import asyncio
import re
import sys

import click

from .cprt import run


@click.command()
@click.option(
    "--pattern",
    "-p",
    "custom_pattern",
    default=None,
    help=(
        "Custom regex with one capture group for the start year. " 'Example: "^Copyright (\\d{4})"'
    ),
)
@click.option(
    "--company",
    "-c",
    "company",
    default=None,
    help="Company name to match in copyright notices.",
)
@click.option(
    "--ext",
    "-e",
    "extensions",
    multiple=True,
    default=["py"],
    help="File extensions to process (without dot), e.g. -e py -e txt",
)
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def main(
    custom_pattern: str | None, company: str, extensions: tuple[str, ...], directory: str
) -> None:
    """CLI tool to update copyright notices in files within DIRECTORY."""
    # Compile custom pattern
    user_re = None
    if custom_pattern:
        try:
            user_re = re.compile(custom_pattern)
        except re.error as e:
            click.echo(f"Invalid custom regex pattern: {e}", err=True)
            sys.exit(1)
    asyncio.run(run(directory, company, user_re, extensions))


if __name__ == "__main__":
    main()
