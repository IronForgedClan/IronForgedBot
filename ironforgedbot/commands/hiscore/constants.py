from strenum import StrEnum
from typing import Dict, TypedDict

EMPTY_SPACE = "⠀⠀"


class Skill(TypedDict):
    name: str
    display_order: int
    emoji_key: str
    xp: int
    level: int
    points: int


class SkillCollection:
    def __init__(self, skills: Dict[str, Skill]):
        self.skills = skills

    def __getattr__(self, key: str):
        if key in self.skills:
            return self.skills[key]
        else:
            raise AttributeError(f"SkillCollection object has no attribute '{key}'")

    def has_skill_name(self, value):
        """
        Check if given value exists as skill name
        """
        for skill in self.skills.values():
            if "name" in skill and skill["name"] == value:
                return True
        return False

    def get_skill_by_long_name(self, value):
        for skill in self.skills.values():
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

SKILLS = SkillCollection(SKILL_DATA)


class ACTIVITIES(StrEnum):
    CLUES_BEGINNER = "Clue Scrolls (beginner)"
    CLUES_EASY = "Clue Scrolls (easy)"
    CLUES_MEDIUM = "Clue Scrolls (medium)"
    CLUES_HARD = "Clue Scrolls (hard)"
    CLUES_ELITE = "Clue Scrolls (elite)"
    CLUES_MASTER = "Clue Scrolls (master)"
    GOTR = "Rifts closed"
    SIRE = "Abyssal Sire"
    HYDRA = "Alchemical Hydra"
    ARTIO = "Artio"
    BARROWS = "Barrows Chests"
    BRYO = "Bryophyta"
    CALLISTO = "Callisto"
    CALV = "Calvar'ion"
    CERB = "Cerberus"
    COX = "Chambers of Xeric"
    COX_CM = "Chambers of Xeric: Challenge Mode"
    CHAOS_ELEMENTAL = "Chaos Elemental"
    CHAOS_FANATIC = "Chaos Fanatic"
    ZILYANA = "Commander Zilyana"
    CORP = "Corporeal Beast"
    CRAZY_ARCHEOLOGIST = "Crazy Archaeologist"
    PRIME = "Dagannoth Prime"
    REX = "Dagannoth Rex"
    SUPREME = "Dagannoth Supreme"
    DERANGED_ARCHEOLOGIST = "Deranged Archaeologist"
    DUKE = "Duke Sucellus"
    GRAARDOR = "General Graardor"
    MOLE = "Giant Mole"
    GROTESQUE = "Grotesque Guardians"
    HESPORI = "Hespori"
    KQ = "Kalphite Queen"
    KBD = "King Black Dragon"
    KRAKEN = "Kraken"
    KREE = "Kree'Arra"
    KRIL = "K'ril Tsutsaroth"
    LUNAR_CHEST = "Lunar Chests"
    MIMIC = "Mimic"
    NEX = "Nex"
    NIGHTMARE = "Nightmare"
    PROSANI_NIGHTMARE = "Phosani's Nightmare"
    OBOR = "Obor"
    MUSPAH = "Phantom Muspah"
    SARACHNIS = "Sarachnis"
    SCORPIA = "Scorpia"
    SCURRIUS = "Scurrius"
    SKOTIZO = "Skotizo"
    SOL = "Sol Heredit"
    SPINDEL = "Spindel"
    TEMP = "Tempoross"
    GAUNTLET = "The Gauntlet"
    CG = "The Corrupted Gauntlet"
    LEVIATHAN = "The Leviathan"
    WHISPERER = "The Whisperer"
    TOB = "Theatre of Blood"
    TOB_HM = "Theatre of Blood: Hard Mode"
    SMOKE_DEVIL = "Thermonuclear Smoke Devil"
    TOA = "Tombs of Amascut"
    TOA_EM = "Tombs of Amascut: Expert Mode"
    ZUK = "TzKal-Zuk"
    JAD = "TzTok-Jad"
    VARDORVIS = "Vardorvis"
    VENENATIS = "Venenatis"
    VETION = "Vet'ion"
    VORK = "Vorkath"
    WT = "Wintertodt"
    ZALCANO = "Zalcano"
    ZULRAH = "Zulrah"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_
