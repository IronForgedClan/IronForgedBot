from dataclasses import dataclass


@dataclass
class AbsentMember:
    id: str
    discord_id: int
    nickname: str
    date: str
    information: str
    comment: str
