from strenum import StrEnum


class SKILLS(StrEnum):
    ATK = "Attack"
    DEF = "Defence"
    STR = "Strength"
    HP = "Hitpoints"
    RANGE = "Ranged"
    PRAYER = "Prayer"
    MAGE = "Magic"
    COOKING = "Cooking"
    WC = "Woodcutting"
    FLETCH = "Fletching"
    FISH = "Fishing"
    FM = "Firemaking"
    CRAFT = "Crafting"
    SMITH = "Smithing"
    MINING = "Mining"
    HERB = "Herblore"
    AGI = "Agility"
    THIEVING = "Thieving"
    SLAYER = "Slayer"
    FARM = "Farming"
    RC = "Runecraft"
    HUNTER = "Hunter"
    CON = "Construction"

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class SKILLS_DISPLAY_ORDER(StrEnum):
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


CLUE_DISPLAY_ORDER = {
    "Clue Scrolls (beginner)": "Beginner",
    "Clue Scrolls (easy)": "Easy",
    "Clue Scrolls (medium)": "Medium",
    "Clue Scrolls (hard)": "Hard",
    "Clue Scrolls (elite)": "Elite",
    "Clue Scrolls (master)": "Master",
}

RAIDS_DISPLAY_ORDER = {
    "Chambers of Xeric": "Chambers of Xeric",
    "Chambers of Xeric: Challenge Mode": "CoX: Challenge Mode",
    "Theatre of Blood": "Theatre of Blood",
    "Theatre of Blood: Hard Mode": "ToB: Hard Mode",
    "Tombs of Amascut": "Tombs of Amascut",
    "Tombs of Amascut: Expert Mode": "ToA: Expert Mode",
}

BOSS_DISPLAY_ORDER = {
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
    "Wintertodt": "Wintertodt",
}


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
