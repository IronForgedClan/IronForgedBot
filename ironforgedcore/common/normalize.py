import re


def normalize_rsn(username: str) -> str:
    """Normalize a RuneScape username for cross-system comparison.

    OSRS treats hyphens, underscores, and spaces as equivalent in
    player names, and comparisons are case-insensitive. Use this
    whenever comparing a name from one system (Discord, DB, WOM,
    hiscores) against a name from another. Never use this for storage
    — always preserve the original casing and characters on write.
    """
    return username.lower().replace("-", " ").replace("_", " ")


def normalize_discord_string(input: str) -> str:
    """Strips string down to plaintext."""
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # Emoticons
        "\U0001f300-\U0001f5ff"  # Symbols & Pictographs
        "\U0001f680-\U0001f6ff"  # Transport & Map Symbols
        "\U0001f700-\U0001f77f"  # Alchemical Symbols
        "\U0001f780-\U0001f7ff"  # Geometric Shapes Extended
        "\U0001f800-\U0001f8ff"  # Supplemental Arrows-C
        "\U0001f900-\U0001f9ff"  # Supplemental Symbols & Pictographs
        "\U0001fa00-\U0001fa6f"  # Chess Symbols, Symbols & Pictographs Extended-A
        "\U0001fa70-\U0001faff"  # Symbols & Pictographs Extended-B
        "\U00002702-\U000027b0"  # Dingbats
        "\U000024c2-\U0001f251"  # Enclosed characters
        "\U00002000-\U0000201f"  # Miscellaneous Symbols
        "\U0000fe00-\U0000fe0f"  # Variation Selectors (used with emojis)
        "\U0001f004"  # Mahjong Tiles
        "\U0001f0cf"  # Playing Cards
        "\U0001f1e0-\U0001f1ff"  # Regional indicator symbols (flags)
        "\U0001f200-\U0001f251"  # Enclosed Alphanumeric Supplement
        "\U0001f004-\U0001f0cf"  # Mahjong Tiles, Playing Cards
        "]+",
        flags=re.UNICODE,
    )
    string_without_emojis = emoji_pattern.sub(r"", input)

    # Only keep characters that are within the ASCII range
    ascii_string = "".join([char for char in string_without_emojis if ord(char) < 128])

    # Replace multiple spaces with a single space and strip leading/trailing spaces
    return re.sub(r"\s+", " ", ascii_string).strip()
