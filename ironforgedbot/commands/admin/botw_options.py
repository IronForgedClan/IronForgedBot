from ironforgedbot.storage.data import BOSSES

BOTW_GROUPS = [
    ["Callisto", "Artio"],
    ["Venenatis", "Spindel"],
    ["Vet'ion", "Calvar'ion"],
]


def get_botw_options() -> list[str]:
    """Get filtered and grouped BOTW options for spinning"""

    exclusions = ["rifts closed", "the gauntlet", "hespori", "mimic"]
    options = [b["name"] for b in BOSSES if b["name"].lower() not in exclusions]

    grouped_names = {name for group in BOTW_GROUPS for name in group}
    combined_options = [o for o in options if o not in grouped_names]

    for group in BOTW_GROUPS:
        present = [name for name in group if name in options]
        if present:
            combined_options.append(" or ".join(present))

    return combined_options
