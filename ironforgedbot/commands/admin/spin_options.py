from ironforgedbot.storage.data import BOSSES, SKILLS, RAIDS


def get_sotw_options() -> list[str]:
    """Get clean list of SOTW options"""
    exclusions = ["attack", "strength", "defence", "hitpoints", "ranged", "magic"]
    return sorted([s["name"] for s in SKILLS if s["name"].lower() not in exclusions])


def get_botw_options() -> list[str]:
    """Get clean list of BOTW options"""
    groups = [
        ["Callisto", "Artio"],
        ["Venenatis", "Spindel"],
        ["Vet'ion", "Calvar'ion"],
    ]
    exclusions = [
        "rifts closed",
        "the gauntlet",
        "hespori",
        "mimic",
        "dagannoth prime",
        "dagannoth rex",
        "dagannoth supreme",
    ]
    options = [b["name"] for b in BOSSES if b["name"].lower() not in exclusions]
    additions = [
        "Dagannoth Kings",
        RAIDS[0]["name"],  # cox
        RAIDS[2]["name"],  # tob
        RAIDS[4]["name"],  # toa
    ]

    grouped_names = {name for group in groups for name in group}
    combined_options = additions + [o for o in options if o not in grouped_names]

    for group in groups:
        present = [name for name in group if name in options]
        if present:
            combined_options.append(" or ".join(present))

    return sorted(combined_options)
