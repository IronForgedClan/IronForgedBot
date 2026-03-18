from ironforgedbot.storage.data import BOSSES, SKILLS


def get_sotw_options() -> list[str]:
    """Get filtered SOTW options for spinning"""
    exclusions = ["attack", "strength", "defence", "hitpoints", "ranged", "magic"]
    return sorted([s["name"] for s in SKILLS if s["name"].lower() not in exclusions])


def get_botw_options() -> list[str]:
    """Get filtered and grouped BOTW options for spinning"""
    groups = [
        ["Callisto", "Artio"],
        ["Venenatis", "Spindel"],
        ["Vet'ion", "Calvar'ion"],
    ]
    exclusions = ["rifts closed", "the gauntlet", "hespori", "mimic"]
    options = [b["name"] for b in BOSSES if b["name"].lower() not in exclusions]

    grouped_names = {name for group in groups for name in group}
    combined_options = [o for o in options if o not in grouped_names]

    for group in groups:
        present = [name for name in group if name in options]
        if present:
            combined_options.append(" or ".join(present))

    return sorted(combined_options)
