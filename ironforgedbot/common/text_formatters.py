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


def text_ul(list: list) -> str:
    output = ""
    for item in list:
        output += f"- {item}{NEW_LINE}"
    return output


def text_ol(list: list) -> str:
    output = ""
    for index, item in enumerate(list):
        output += f"{index+1}. {item}{NEW_LINE}"
    return output


def text_quote(input: str) -> str:
    return f"> {input}{NEW_LINE}"


def text_quote_multiline(input: str) -> str:
    return f">>> {input}{NEW_LINE}"


def text_code(input: str) -> str:
    return f"`{input}`"


def text_code_block(input: str) -> str:
    return f"```{input}```"
