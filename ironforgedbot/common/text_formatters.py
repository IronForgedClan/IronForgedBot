import textwrap
from collections.abc import Sequence

from tabulate import tabulate

from ironforgedbot.common.constants import NEW_LINE


def text_bold(input: str) -> str:
    return f"**{input}**"


def text_italic(input: str) -> str:
    return f"_{input}_"


def text_bold_italics(input: str) -> str:
    return f"***{input}***"


def text_underline(input: str) -> str:
    return f"__{input}__"


def text_sub(input: str) -> str:
    return f"-# {input}{NEW_LINE}"


def text_link(title: str, link: str) -> str:
    return f"[{title}]({link})"


def text_h1(input: str) -> str:
    return f"# {input}{NEW_LINE}"


def text_h2(input: str) -> str:
    return f"## {input}{NEW_LINE}"


def text_h3(input: str) -> str:
    return f"### {input}{NEW_LINE}"


def text_ul(input_list: list) -> str:
    output = ""
    for item in input_list:
        output += f"- {item}{NEW_LINE}"
    return output


def text_ol(list: list) -> str:
    output = ""
    for index, item in enumerate(list):
        output += f"{index + 1}. {item}{NEW_LINE}"
    return output


def text_quote(input: str) -> str:
    return f"> {input}{NEW_LINE}"


def text_quote_multiline(input: str) -> str:
    return f">>> {input}{NEW_LINE}"


def text_code(input: str) -> str:
    return f"`{input}`"


def text_code_block(input: str) -> str:
    return f"```{input}```"


def _wrap_cell(value: str, width: int | None) -> str:
    if width is None or not value:
        return value
    wrapped = textwrap.wrap(
        value,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    )
    return "\n".join(wrapped) if wrapped else value


def text_ascii_table(
    rows: Sequence[Sequence[str]],
    headers: Sequence[str] = (),
    *,
    wrap_widths: Sequence[int | None] | None = None,
    tablefmt: str = "simple",
    colalign: Sequence[str] | None = None,
    code_block: bool = True,
) -> str:
    """Render rows as a tabulate ASCII table, optionally wrapped in a code block.

    Args:
        rows: Data rows; one tuple/list per row, one entry per column.
        headers: Column headers. Pass an empty sequence to omit the header row.
        wrap_widths: Per-column max character widths aligned to ``headers``.
            ``None`` (or omitting the index) leaves a column unwrapped. Wraps
            with ``textwrap.wrap(..., break_long_words=True,
            break_on_hyphens=False)`` so single words longer than the width
            still break.
        tablefmt: One of the formats supported by ``tabulate``. Defaults to
            ``"simple"``.
        colalign: Per-column alignment ("left", "right", "center"); passed
            straight through to ``tabulate``.
        code_block: When True (default), wrap the rendered table in a fenced
            code block so Discord renders it monospaced.

    Returns:
        The formatted table string (code-blocked when ``code_block=True``).
    """
    if wrap_widths:
        widths = list(wrap_widths) + [None] * (len(headers) - len(wrap_widths))
        rows = [
            tuple(_wrap_cell(cell, w) for cell, w in zip(row, widths, strict=False))
            for row in rows
        ]
    table = tabulate(
        rows,
        headers=list(headers),
        tablefmt=tablefmt,
        colalign=colalign,
    )
    return text_code_block(table) if code_block else table
