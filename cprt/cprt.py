"""All the core functionality of the code base is defined here."""

from __future__ import annotations

import asyncio
import datetime
from pathlib import Path
import re

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
        super().__init__()
        self.current_year = current_year
        self.company = company
        self.custom_pattern = custom_pattern
        if not self.custom_pattern:
            escaped = re.escape(company)
            self.range_pattern = re.compile(rf"Copyright (\d{{4}})-(\d{{4}}) ({escaped})")
            self.single_pattern = re.compile(rf"Copyright (\d{{4}}) ({escaped})")

    def _update_comment(self, comment_text: str) -> str:
        text = comment_text.lstrip("# ").rstrip()
        # Custom pattern
        if self.custom_pattern:
            m = self.custom_pattern.match(text)
            if m:
                start = m.group(1)
                return f"# Copyright {start}-{self.current_year} {self.company}"
            return comment_text
        # Default patterns
        m_range = self.range_pattern.match(text)
        if m_range:
            start, _, comp = m_range.groups()
            return f"# Copyright {start}-{self.current_year} {comp}"
        m_single = self.single_pattern.match(text)
        if m_single:
            start, comp = m_single.groups()
            return f"# Copyright {start}-{self.current_year} {comp}"
        return comment_text

    def leave_EmptyLine(  # noqa: N802
        self, original: cst.EmptyLine, updated: cst.EmptyLine
    ) -> cst.EmptyLine:
        if updated.comment:
            new_val = self._update_comment(updated.comment.value)
            if new_val != updated.comment.value:
                return updated.with_changes(comment=cst.Comment(new_val))
        return updated

    def leave_TrailingWhitespace(  # noqa: N802
        self, original: cst.TrailingWhitespace, updated: cst.TrailingWhitespace
    ) -> cst.TrailingWhitespace:
        if updated.comment:
            new_val = self._update_comment(updated.comment.value)
            if new_val != updated.comment.value:
                return updated.with_changes(comment=cst.Comment(new_val))
        return updated


async def run(
    directory: str,
    company: str,
    custom_pattern: re.Pattern | None,
    extensions: tuple[str, ...],
) -> None:
    current_year = datetime.datetime.now().year
    tasks = []
    exts = {f".{e.lstrip('.')}" for e in extensions}
    for file_path in Path(directory).rglob("*"):
        if file_path.is_file() and file_path.suffix in exts:
            if file_path.suffix == ".py":
                tasks.append(process_py_file(file_path, current_year, company, custom_pattern))
            else:
                tasks.append(process_text_file(file_path, current_year, company, custom_pattern))
    await asyncio.gather(*tasks)


async def process_py_file(
    file_path: Path,
    current_year: int,
    company: str,
    custom_pattern: re.Pattern | None,
) -> None:
    try:
        content = await aiofiles.open(file_path, encoding="utf-8").read()
    except Exception as e:
        click.echo(f"Error reading {file_path}: {e}", err=True)
        return

    try:
        module = cst.parse_module(content)
        transformer = CopyrightTransformer(current_year, company, custom_pattern)
        new_module = module.visit(transformer)
        new_source = new_module.code
        if new_source != content:
            await aiofiles.open(file_path, "w", encoding="utf-8").write(new_source)
            click.echo(f"Updated copyright notice in: {file_path}")
    except Exception as e:
        click.echo(f"Error processing {file_path}: {e}", err=True)


async def process_text_file(
    file_path: Path,
    current_year: int,
    company: str,
    custom_pattern: re.Pattern | None,
) -> None:
    try:
        async with aiofiles.open(file_path, encoding="utf-8") as f:
            lines = await f.readlines()
    except Exception as e:
        click.echo(f"Error reading {file_path}: {e}", err=True)
        return

    escaped = re.escape(company)
    range_pat = (
        custom_pattern
        if custom_pattern
        else re.compile(rf"Copyright (\d{{4}})-(\d{{4}}) ({escaped})")
    )
    single_pat = (
        custom_pattern if custom_pattern else re.compile(rf"Copyright (\d{{4}}) ({escaped})")
    )

    updated = []
    modified = False
    for line in lines:
        text = line.rstrip("\n")
        m_range = range_pat.match(text)
        if m_range:
            start = m_range.group(1)
            updated.append(f"Copyright {start}-{current_year} {company}\n")
            modified = True
            continue
        m_single = single_pat.match(text)
        if m_single:
            start = m_single.group(1)
            updated.append(f"Copyright {start}-{current_year} {company}\n")
            modified = True
            continue
        updated.append(line)

    if modified:
        try:
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.writelines(updated)
            click.echo(f"Updated copyright notice in: {file_path}")
        except Exception as e:
            click.echo(f"Error writing {file_path}: {e}", err=True)
