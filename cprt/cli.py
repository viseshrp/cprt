"""The console script for cprt."""

import asyncio
import datetime
from pathlib import Path
import re
import sys

import aiofiles
import click
import libcst as cst


class CopyrightTransformer(cst.CSTTransformer):
    """
    A LibCST transformer that updates copyright comments with full precision,
    preserving formatting and only modifying comment tokens.
    """

    def __init__(
        self, current_year: int, company: str, custom_pattern: re.Pattern | None = None
    ) -> None:
        self.current_year = current_year
        self.company = company
        self.custom_pattern = custom_pattern
        if not self.custom_pattern:
            # Build default patterns based on company
            escaped = re.escape(company)
            self.range_pattern = re.compile(rf"Copyright (\d{{4}})-(\d{{4}}) ({escaped})")
            self.single_pattern = re.compile(rf"Copyright (\d{{4}}) ({escaped})")

    def _update_comment(self, comment_text: str) -> str:
        # Strip leading '#' and whitespace
        text = comment_text.lstrip("# ").rstrip()
        # If custom regex provided, use it to extract start year
        if self.custom_pattern:
            m = self.custom_pattern.match(text)
            if m:
                start = m.group(1)
                return f"# Copyright {start}-{self.current_year} {self.company}"
            return comment_text

        # Otherwise use default patterns
        m_range = self.range_pattern.match(text)
        if m_range:
            start, _, comp = m_range.groups()
            return f"# Copyright {start}-{self.current_year} {comp}"

        m_single = self.single_pattern.match(text)
        if m_single:
            start, comp = m_single.groups()
            return f"# Copyright {start}-{self.current_year} {comp}"

        # No match, return original
        return comment_text

    def leave_EmptyLine(self, original: cst.EmptyLine, updated: cst.EmptyLine) -> cst.EmptyLine:
        if updated.comment:
            new_val = self._update_comment(updated.comment.value)
            if new_val != updated.comment.value:
                return updated.with_changes(comment=cst.Comment(new_val))
        return updated

    def leave_TrailingWhitespace(
        self, original: cst.TrailingWhitespace, updated: cst.TrailingWhitespace
    ) -> cst.TrailingWhitespace:
        if updated.comment:
            new_val = self._update_comment(updated.comment.value)
            if new_val != updated.comment.value:
                return updated.with_changes(comment=cst.Comment(new_val))
        return updated


@click.command()
@click.option(
    "--pattern",
    "-p",
    "custom_pattern",
    default=None,
    help=(
        "Custom regex with one capture group for the start year. "
        'Example: "r"^Copyright (\\d{4})""'
    ),
)
@click.option(
    "--company",
    "-c",
    "company",
    default="ANSYS, Inc.",
    show_default=True,
    help="Company name to match in copyright notices.",
)
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True))
def main(custom_pattern: str | None, company: str, directory: str) -> None:
    """CLI tool to update copyright notices in files within DIRECTORY."""
    # Compile custom pattern if provided
    if custom_pattern:
        try:
            user_re = re.compile(custom_pattern)
        except re.error as e:
            click.echo(f"Invalid custom regex pattern: {e}", err=True)
            sys.exit(1)
    else:
        user_re = None

    asyncio.run(run(directory, company, user_re))


async def run(directory: str, company: str, custom_pattern: re.Pattern | None) -> None:
    current_year = datetime.datetime.now().year
    tasks = []
    for file_path in Path(directory).rglob("*"):
        if file_path.is_file() and file_path.suffix in {".py", ".txt", ".md"}:
            tasks.append(process_file(file_path, current_year, company, custom_pattern))
    await asyncio.gather(*tasks)


async def process_file(
    file_path: Path, current_year: int, company: str, custom_pattern: re.Pattern | None
) -> None:
    try:
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            source = await f.read()

        module = cst.parse_module(source)
        transformer = CopyrightTransformer(current_year, company, custom_pattern)
        new_module = module.visit(transformer)
        new_source = new_module.code

        if new_source != source:
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(new_source)
            click.echo(f"Updated copyright notice in: {file_path}")

    except Exception as e:
        click.echo(f"Error processing {file_path}: {e}", err=True)


if __name__ == "__main__":
    main()
