from apscheduler.executors.base import logging
from discord import Emoji
from strenum import StrEnum
from collections.abc import Sequence

emojiCache = dict[str, Emoji]()

def find_emoji(list: Sequence[Emoji], target: str):
    if target in emojiCache:
        return emojiCache[target]

    for emoji in list:
        if emoji.available and emoji.name == target:
            emojiCache[emoji.name] = emoji
            return emoji

    logging.warn(f"Requested emoji '{target}' not found")
    return ""

class SKILLS_TO_EMOJI(StrEnum):
    ATK = "Attack"
    HP = "Hitpoints"
    MINING = "Mining"
    STR = "Strength"
    AGI = "Agility"
    SMITH = "Smithing"
    DEF = "Defence"
    HERB = "Herblore"
    FISH = "Fishing"
    RANGE = "Ranged"
    THIEVING = "Thieving"
    COOKING = "Cooking"
    PRAYER = "Prayer"
    CRAFT = "Crafting"
    FM = "Firemaking"
    MAGE = "Magic"
    FLETCH = "Fletching"
    WC = "Woodcutting"
    RC = "Runecraft"
    SLAYER = "Slayer"
    FARM = "Farming"
    CON = "Construction"
    HUNTER = "Hunter"


CLUE_TO_EMOJI = {
    "Clue Scrolls (beginner)": "Beginner",
    "Clue Scrolls (easy)": "Easy",
    "Clue Scrolls (medium)": "Medium",
    "Clue Scrolls (hard)": "Hard",
    "Clue Scrolls (elite)": "Elite",
    "Clue Scrolls (master)": "Master",
}

RAIDS_TO_EMOJI = {
    "Chambers of Xeric": "Chambers of Xeric",
    "Chambers of Xeric: Challenge Mode": "CoX: Challenge Mode",
    "Theatre of Blood": "Theatre of Blood",
    "Theatre of Blood: Hard Mode": "ToB: Hard Mode",
    "Tombs of Amascut": "Tombs of Amascut",
    "Tombs of Amascut: Expert Mode": "ToA: Expert Mode",
}

BOSS_TO_EMOJI = {
    "Rifts closed": "Guardians of the Rift",
    "Abyssal Sire": "Abyssal Sire",
    "Alchemical Hydra": "Alchemical Hydra",
    "Artio": "Artio",
    "Barrows Chests": "Barrows Chests",
    "Bryophyta": "Bryophyta",
    "Callisto": "Callisto",
    "Calvar'ion": "Calvar'ion",
    "Cerberus": "Cerberus",
    "Chaos Elemental": "Chaos Elemental",
    "Chaos Fanatic": "Chaos Fanatic",
    "Commander Zilyana": "Commander Zilyana",
    "Corporeal Beast": "Corporeal Beast",
    "Crazy Archaeologist": "Crazy Archaeologist",
    "Dagannoth Prime": "Dagannoth Prime",
    "Dagannoth Rex": "Dagannoth Rex",
    "Dagannoth Supreme": "Dagannoth Supreme",
    "Deranged Archaeologist": "Deranged Archaeologist",
    "Duke Sucellus": "Duke Sucellus",
    "General Graardor": "General Graardor",
    "Giant Mole": "Giant Mole",
    "Grotesque Guardians": "Grotesque Guardians",
    "Hespori": "Hespori",
    "Kalphite Queen": "Kalphite Queen",
    "King Black Dragon": "King Black Dragon",
    "Kraken": "Kraken",
    "Kree'Arra": "Kree'Arra",
    "K'ril Tsutsaroth": "K'ril Tsutsaroth",
    "Lunar Chests": "Lunar Chests",
    "Mimic": "Mimic",
    "Nex": "Nex",
    "Nightmare": "Nightmare",
    "Phosani's Nightmare": "Phosani's Nightmare",
    "Obor": "Obor",
    "Phantom Muspah": "Phantom Muspah",
    "Sarachnis": "Sarachnis",
    "Scorpia": "Scorpia",
    "Scurrius": "Scurrius",
    "Skotizo": "Skotizo",
    "Sol Heredit": "Sol Heredit",
    "Spindel": "Spindel",
    "Tempoross": "Tempoross",
    "The Gauntlet": "The Gauntlet",
    "The Corrupted Gauntlet": "thecorruptedgauntlet",
    "The Leviathan": "The Leviathan",
    "The Whisperer": "The Whisperer",
    "Thermonuclear Smoke Devil": "Thermonuclear Smoke Devil",
    "TzKal-Zuk": "TzKal-Zuk",
    "TzTok-Jad": "TzTok-Jad",
    "Vardorvis": "Vardorvis",
    "Venenatis": "Venenatis",
    "Vet'ion": "Vet'ion",
    "Vorkath": "Vorkath",
    "Wintertodt": "wintertodt",
}

