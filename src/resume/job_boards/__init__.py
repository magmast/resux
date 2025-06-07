from typing import TypedDict


class Skill(TypedDict):
    name: str
    optional: bool
    level: str | None


class Posting(TypedDict):
    title: str
    description: str
    skills: list[Skill]
