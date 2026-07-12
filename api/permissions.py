import enum


class PERM(enum.StrEnum):
    META_READ = "meta:read"
    MEMBERS_READ = "members:read"
    MEMBERS_LIST = "members:list"
    INGOTS_READ = "ingots:read"
    INGOTS_READ_TRANSACTIONS = "ingots:read:transactions"
    SCORES_READ = "scores:read"
    SCORES_READ_HISTORY = "scores:read:history"


KNOWN_PERMS: list[tuple[str, str]] = [
    (PERM.META_READ, "Access /health and /version"),
    (PERM.MEMBERS_READ, "Read a single member record"),
    (PERM.MEMBERS_LIST, "List member directory"),
    (PERM.INGOTS_READ, "Read member ingot balances"),
    (PERM.INGOTS_READ_TRANSACTIONS, "Read ingot transaction history"),
    (PERM.SCORES_READ, "Read player score breakdowns"),
    (PERM.SCORES_READ_HISTORY, "Read player score history"),
]


KNOWN_PERM_NAMES: frozenset[str] = frozenset(name for name, _ in KNOWN_PERMS)
