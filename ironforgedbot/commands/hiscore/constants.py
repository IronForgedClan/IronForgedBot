from typing import Dict, NotRequired, TypedDict, Union

EMPTY_SPACE = "⠀⠀"


class Skill(TypedDict):
    name: str
    display_order: int
    emoji_key: str
    xp: int
    level: int
    points: int


class Activity(TypedDict):
    name: str
    display_name: NotRequired[str]
    display_order: int
    emoji_key: str
    kc: int
    points: int


class Collection:
    def __init__(self, items: Union[Dict[str, Skill], Dict[str, Activity]]):
        self.items = items

    def __getattr__(self, key: str):
        if key in self.items:
            return self.items[key]
        else:
            raise AttributeError(f"Collection object has no attribute '{key}'")

    def has_item_name(self, value):
        """
        Check if given value exists as skill name
        """
        for skill in self.items.values():
            if "name" in skill and skill["name"] == value:
                return True
        return False

    def get_item_by_name(self, value):
        for skill in self.items.values():
            if "name" in skill and skill["name"] == value:
                return skill
        return None


SKILL_DATA: Dict[str, Skill] = {
    "ATK": {
        "name": "Attack",
        "display_order": 1,
        "emoji_key": "Attack",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "DEF": {
        "name": "Defence",
        "display_order": 7,
        "emoji_key": "Defence",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "STR": {
        "name": "Strength",
        "display_order": 4,
        "emoji_key": "Strength",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "HP": {
        "name": "Hitpoints",
        "display_order": 2,
        "emoji_key": "Hitpoints",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "RANGE": {
        "name": "Ranged",
        "display_order": 10,
        "emoji_key": "Ranged",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "PRAYER": {
        "name": "Prayer",
        "display_order": 13,
        "emoji_key": "Prayer",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "MAGE": {
        "name": "Magic",
        "display_order": 16,
        "emoji_key": "Magic",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "COOKING": {
        "name": "Cooking",
        "display_order": 12,
        "emoji_key": "Cooking",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "WC": {
        "name": "Woodcutting",
        "display_order": 18,
        "emoji_key": "Woodcutting",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "FLETCH": {
        "name": "Fletching",
        "display_order": 17,
        "emoji_key": "Fletching",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "FISH": {
        "name": "Fishing",
        "display_order": 9,
        "emoji_key": "Fishing",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "FM": {
        "name": "Firemaking",
        "display_order": 15,
        "emoji_key": "Firemaking",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "CRAFT": {
        "name": "Crafting",
        "display_order": 14,
        "emoji_key": "Crafting",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "SMITH": {
        "name": "Smithing",
        "display_order": 6,
        "emoji_key": "Smithing",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "MINING": {
        "name": "Mining",
        "display_order": 3,
        "emoji_key": "Mining",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "HERB": {
        "name": "Herblore",
        "display_order": 8,
        "emoji_key": "Herblore",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "AGI": {
        "name": "Agility",
        "display_order": 5,
        "emoji_key": "Agility",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "THIEVING": {
        "name": "Thieving",
        "display_order": 11,
        "emoji_key": "Thieving",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "SLAYER": {
        "name": "Slayer",
        "display_order": 20,
        "emoji_key": "Slayer",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "FARM": {
        "name": "Farming",
        "display_order": 21,
        "emoji_key": "Farming",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "RC": {
        "name": "Runecraft",
        "display_order": 19,
        "emoji_key": "Runecraft",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "HUNTER": {
        "name": "Hunter",
        "display_order": 23,
        "emoji_key": "Hunter",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
    "CON": {
        "name": "Construction",
        "display_order": 22,
        "emoji_key": "Construction",
        "xp": 0,
        "points": 0,
        "level": 0,
    },
}

SKILLS = Collection(SKILL_DATA)


CLUE_DATA: Dict[str, Activity] = {
    "BEGINNER": {
        "name": "Clue Scrolls (beginner)",
        "display_name": "Beginner",
        "display_order": 1,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "EASY": {
        "name": "Clue Scrolls (easy)",
        "display_name": "Easy",
        "display_order": 2,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "MEDIUM": {
        "name": "Clue Scrolls (medium)",
        "display_name": "Medium",
        "display_order": 3,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "HARD": {
        "name": "Clue Scrolls (hard)",
        "display_name": "Hard",
        "display_order": 4,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "ELITE": {
        "name": "Clue Scrolls (elite)",
        "display_name": "Elite",
        "display_order": 5,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "MASTER": {
        "name": "Clue Scrolls (master)",
        "display_name": "Master",
        "display_order": 6,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
}

CLUES = Collection(CLUE_DATA)

RAID_DATA: Dict[str, Activity] = {
    "COX": {
        "name": "Chambers of Xeric",
        "display_order": 1,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "COX_CM": {
        "name": "Chambers of Xeric: Challenge Mode",
        "display_order": 2,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "TOB": {
        "name": "Theatre of Blood",
        "display_order": 3,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "TOB_HM": {
        "name": "Theatre of Blood: Hard Mode",
        "display_order": 4,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "TOA": {
        "name": "Tombs of Amascut",
        "display_order": 4,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
    "TOA_EM": {
        "name": "Tombs of Amascut: Expert Mode",
        "display_order": 4,
        "emoji_key": "clue",
        "kc": 0,
        "points": 0,
    },
}

RAIDS = Collection(RAID_DATA)

BOSS_DATA: Dict[str, Activity] = {
    "GOTR": {
        "name": "Rifts closed",
        "display_order": 1,
        "emoji_key": "Rifts closed",
        "kc": 0,
        "points": 0,
    },
    "SIRE": {
        "name": "Abyssal Sire",
        "display_order": 2,
        "emoji_key": "Abyssal Sire",
        "kc": 0,
        "points": 0,
    },
    "HYDRA": {
        "name": "Alchemical Hydra",
        "display_order": 3,
        "emoji_key": "Alchemical Hydra",
        "kc": 0,
        "points": 0,
    },
    "ARTIO": {
        "name": "Artio",
        "display_order": 4,
        "emoji_key": "Artio",
        "kc": 0,
        "points": 0,
    },
    "BARROWS": {
        "name": "Barrows Chests",
        "display_order": 5,
        "emoji_key": "Barrows Chests",
        "kc": 0,
        "points": 0,
    },
    "BRYO": {
        "name": "Bryophyta",
        "display_order": 6,
        "emoji_key": "Bryophyta",
        "kc": 0,
        "points": 0,
    },
    "CALLISTO": {
        "name": "Callisto",
        "display_order": 7,
        "emoji_key": "Callisto",
        "kc": 0,
        "points": 0,
    },
    "CALV": {
        "name": "Calvar'ion",
        "display_order": 8,
        "emoji_key": "Calvar'ion",
        "kc": 0,
        "points": 0,
    },
    "CERB": {
        "name": "Cerberus",
        "display_order": 9,
        "emoji_key": "Cerberus",
        "kc": 0,
        "points": 0,
    },
    "CHAOS_ELEMENTAL": {
        "name": "Chaos Elemental",
        "display_order": 10,
        "emoji_key": "Chaos Elemental",
        "kc": 0,
        "points": 0,
    },
    "CHAOS_FANATIC": {
        "name": "Chaos Fanatic",
        "display_order": 11,
        "emoji_key": "Chaos Fanatic",
        "kc": 0,
        "points": 0,
    },
    "ZILYANA": {
        "name": "Commander Zilyana",
        "display_order": 12,
        "emoji_key": "Commander Zilyana",
        "kc": 0,
        "points": 0,
    },
    "CORP": {
        "name": "Corporeal Beast",
        "display_order": 13,
        "emoji_key": "Corporeal Beast",
        "kc": 0,
        "points": 0,
    },
    "CRAZY_ARCHEOLOGIST": {
        "name": "Crazy Archaeologist",
        "display_order": 14,
        "emoji_key": "Crazy Archaeologist",
        "kc": 0,
        "points": 0,
    },
    "PRIME": {
        "name": "Dagannoth Prime",
        "display_order": 15,
        "emoji_key": "Dagannoth Prime",
        "kc": 0,
        "points": 0,
    },
    "REX": {
        "name": "Dagannoth Rex",
        "display_order": 16,
        "emoji_key": "Dagannoth Rex",
        "kc": 0,
        "points": 0,
    },
    "SUPREME": {
        "name": "Dagannoth Supreme",
        "display_order": 17,
        "emoji_key": "Dagannoth Supreme",
        "kc": 0,
        "points": 0,
    },
    "DERANGED_ARCHEOLOGIST": {
        "name": "Deranged Archaeologist",
        "display_order": 18,
        "emoji_key": "Deranged Archaeologist",
        "kc": 0,
        "points": 0,
    },
    "DUKE": {
        "name": "Duke Sucellus",
        "display_order": 19,
        "emoji_key": "Duke Sucellus",
        "kc": 0,
        "points": 0,
    },
    "GRAARDOR": {
        "name": "General Graardor",
        "display_order": 20,
        "emoji_key": "General Graardor",
        "kc": 0,
        "points": 0,
    },
    "MOLE": {
        "name": "Giant Mole",
        "display_order": 21,
        "emoji_key": "Giant Mole",
        "kc": 0,
        "points": 0,
    },
    "GROTESQUE": {
        "name": "Grotesque Guardians",
        "display_order": 22,
        "emoji_key": "Grotesque Guardians",
        "kc": 0,
        "points": 0,
    },
    "HESPORI": {
        "name": "Hespori",
        "display_order": 23,
        "emoji_key": "Hespori",
        "kc": 0,
        "points": 0,
    },
    "KQ": {
        "name": "Kalphite Queen",
        "display_order": 24,
        "emoji_key": "Kalphite Queen",
        "kc": 0,
        "points": 0,
    },
    "KBD": {
        "name": "King Black Dragon",
        "display_order": 25,
        "emoji_key": "King Black Dragon",
        "kc": 0,
        "points": 0,
    },
    "KRAKEN": {
        "name": "Kraken",
        "display_order": 26,
        "emoji_key": "Kraken",
        "kc": 0,
        "points": 0,
    },
    "KREE": {
        "name": "Kree'Arra",
        "display_order": 27,
        "emoji_key": "Kree'Arra",
        "kc": 0,
        "points": 0,
    },
    "KRIL": {
        "name": "K'ril Tsutsaroth",
        "display_order": 28,
        "emoji_key": "K'ril Tsutsaroth",
        "kc": 0,
        "points": 0,
    },
    "LUNAR_CHEST": {
        "name": "Lunar Chests",
        "display_order": 29,
        "emoji_key": "Lunar Chests",
        "kc": 0,
        "points": 0,
    },
    "MIMIC": {
        "name": "Mimic",
        "display_order": 30,
        "emoji_key": "Mimic",
        "kc": 0,
        "points": 0,
    },
    "NEX": {
        "name": "Nex",
        "display_order": 31,
        "emoji_key": "Nex",
        "kc": 0,
        "points": 0,
    },
    "NIGHTMARE": {
        "name": "Nightmare",
        "display_order": 32,
        "emoji_key": "Nightmare",
        "kc": 0,
        "points": 0,
    },
    "PROSANI_NIGHTMARE": {
        "name": "Phosani's Nightmare",
        "display_order": 33,
        "emoji_key": "Phosani's Nightmare",
        "kc": 0,
        "points": 0,
    },
    "OBOR": {
        "name": "Obor",
        "display_order": 34,
        "emoji_key": "Obor",
        "kc": 0,
        "points": 0,
    },
    "MUSPAH": {
        "name": "Phantom Muspah",
        "display_order": 35,
        "emoji_key": "Phantom Muspah",
        "kc": 0,
        "points": 0,
    },
    "SARACHNIS": {
        "name": "Sarachnis",
        "display_order": 36,
        "emoji_key": "Sarachnis",
        "kc": 0,
        "points": 0,
    },
    "SCORPIA": {
        "name": "Scorpia",
        "display_order": 37,
        "emoji_key": "Scorpia",
        "kc": 0,
        "points": 0,
    },
    "SCURRIUS": {
        "name": "Scurrius",
        "display_order": 38,
        "emoji_key": "Scurrius",
        "kc": 0,
        "points": 0,
    },
    "SKOTIZO": {
        "name": "Skotizo",
        "display_order": 39,
        "emoji_key": "Skotizo",
        "kc": 0,
        "points": 0,
    },
    "SOL": {
        "name": "Sol Heredit",
        "display_order": 40,
        "emoji_key": "Sol Heredit",
        "kc": 0,
        "points": 0,
    },
    "SPINDEL": {
        "name": "Spindel",
        "display_order": 41,
        "emoji_key": "Spindel",
        "kc": 0,
        "points": 0,
    },
    "TEMP": {
        "name": "Tempoross",
        "display_order": 42,
        "emoji_key": "Tempoross",
        "kc": 0,
        "points": 0,
    },
    "GAUNTLET": {
        "name": "The Gauntlet",
        "display_order": 43,
        "emoji_key": "The Gauntlet",
        "kc": 0,
        "points": 0,
    },
    "CG": {
        "name": "The Corrupted Gauntlet",
        "display_order": 44,
        "emoji_key": "The Corrupted Gauntlet",
        "kc": 0,
        "points": 0,
    },
    "LEVIATHAN": {
        "name": "The Leviathan",
        "display_order": 45,
        "emoji_key": "The Leviathan",
        "kc": 0,
        "points": 0,
    },
    "WHISPERER": {
        "name": "The Whisperer",
        "display_order": 46,
        "emoji_key": "The Whisperer",
        "kc": 0,
        "points": 0,
    },
    "SMOKE_DEVIL": {
        "name": "Thermonuclear Smoke Devil",
        "display_order": 47,
        "emoji_key": "Thermonuclear Smoke Devil",
        "kc": 0,
        "points": 0,
    },
    "ZUK": {
        "name": "TzKal-Zuk",
        "display_order": 48,
        "emoji_key": "TzKal-Zuk",
        "kc": 0,
        "points": 0,
    },
    "JAD": {
        "name": "TzTok-Jad",
        "display_order": 49,
        "emoji_key": "TzTok-Jad",
        "kc": 0,
        "points": 0,
    },
    "VARDORVIS": {
        "name": "Vardorvis",
        "display_order": 50,
        "emoji_key": "Vardorvis",
        "kc": 0,
        "points": 0,
    },
    "VENENATIS": {
        "name": "Venenatis",
        "display_order": 51,
        "emoji_key": "Venenatis",
        "kc": 0,
        "points": 0,
    },
    "VETION": {
        "name": "Vet'ion",
        "display_order": 52,
        "emoji_key": "Vet'ion",
        "kc": 0,
        "points": 0,
    },
    "VORK": {
        "name": "Vorkath",
        "display_order": 53,
        "emoji_key": "Vorkath",
        "kc": 0,
        "points": 0,
    },
    "WT": {
        "name": "Wintertodt",
        "display_order": 54,
        "emoji_key": "Wintertodt",
        "kc": 0,
        "points": 0,
    },
    "ZALCANO": {
        "name": "Zalcano",
        "display_order": 55,
        "emoji_key": "Zalcano",
        "kc": 0,
        "points": 0,
    },
    "ZULRAH": {
        "name": "Zulrah",
        "display_order": 56,
        "emoji_key": "Zulrah",
        "kc": 0,
        "points": 0,
    },
}

IGNORED_ACTIVITIES = {
    "LEAGUE": "League Points",
    "DEADMAN": "Deadman Points",
    "BH": "Bounty Hunter - Hunter",
    "BH_ROGUE": "Bounty Hunter - Rogue",
    "BH_LEGACY": "Bounty Hunter (Legacy)",
    "BH_LEGACY_HUNT": "Bounty Hunter (Legacy) - Hunter",
    "BH_LEGACY_ROGUE": "Bounty Hunter (Legacy) - Rogue",
    "CLUES_ALL": "Clue Scrolls (all)",
    "LMS": "LMS - Rank",
    "PVP_ARENA": "PvP Arena - Rank",
    "SOULWARS": "Soul Wars Zeal",
    "COLOSSEUM": "Colosseum Glory",
}

BOSSES = Collection(BOSS_DATA)
ACTIVITIES = Collection({**CLUE_DATA, **RAID_DATA, **BOSS_DATA})
