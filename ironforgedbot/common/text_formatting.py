# Target character width for spoiler tags (makes all spoiler bars roughly same length)
SPOILER_WIDTH = 100

# These characters render narrower in Discord's font
NARROW_CHARS = set("ilIjtfr'")

# These characters render wider in Discord's font
WIDE_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVXYZmw ")

NARROW_MULTIPLIER = 0.5
WIDE_MULTIPLIER = 2
NORMAL_MULTIPLIER = 1.0


def calculate_visual_width(text: str) -> float:
    """Calculate approximate visual width of text in Discord's proportional font"""
    visual_width = 0.0

    for char in text:
        if ord(char) > 0x1F000:  # Simple emoji detection (most emojis > U+1F000)
            continue

        if char in NARROW_CHARS:
            visual_width += NARROW_MULTIPLIER
        elif char in WIDE_CHARS:
            visual_width += WIDE_MULTIPLIER
        else:
            visual_width += NORMAL_MULTIPLIER

    return visual_width


def pad_winner_text(
    emoji: str, winner: str, target_width: float = SPOILER_WIDTH
) -> str:
    """Pad winner text based on visual width to reach target_width, centered"""
    base_text = f"{emoji} {winner}"
    current_visual_width = calculate_visual_width(base_text)
    padding_needed = target_width - current_visual_width

    if padding_needed <= 0:
        return base_text

    pad_char = " "

    left_padding = int(padding_needed / 2)
    right_padding = int(padding_needed) - left_padding

    return (pad_char * left_padding) + base_text + (pad_char * right_padding)
