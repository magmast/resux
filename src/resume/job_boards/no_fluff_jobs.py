from contextlib import AsyncExitStack
import json
from types import TracebackType
from typing import Annotated, Any, Literal, Self

import httpx
from pydantic import BaseModel, Field
from selectolax.parser import HTMLParser

from resume.job_boards import Posting


class _Specs(BaseModel):
    daily_tasks: Annotated[list[str], Field(alias="dailyTasks")]


class _Company(BaseModel):
    name: str
    size: str


class _Details(BaseModel):
    description: str


class _OperatingSystems(BaseModel):
    linux: Annotated[bool, Field(alias="lin")]
    mac: bool
    windows: Annotated[bool, Field(alias="win")]


class _Equipment(BaseModel):
    computer: str
    monitors: str
    operating_systems: Annotated[_OperatingSystems, Field(alias="operatingSystems")]
    office_perks: Annotated[list[str], Field(alias="officePerks")]


class _Benefits(BaseModel):
    benefits: list[str]
    equipment: _Equipment


class _Country(BaseModel):
    code: str
    name: str


class _GeoLocation(BaseModel):
    latitude: float
    longitude: float


class _Place(BaseModel):
    country: _Country | None = None
    city: Literal["Remote"] | str | None = None
    street: str | None = None
    postal_code: Annotated[str | None, Field(alias="postalCode")] = None
    geo_location: Annotated[_GeoLocation | None, Field(alias="geoLocation")] = None
    url: str


class _Location(BaseModel):
    places: list[_Place]
    remote: int
    multi_city_count: Annotated[int, Field(alias="multicityCount")]
    covid_time_remotely: Annotated[bool, Field(alias="covidTimeRemotely")]
    remote_flexible: Annotated[bool, Field(alias="remoteFlexible")]
    fieldwork: bool
    default_index: Annotated[int, Field(alias="defaultIndex")]
    hybrid_desc: Annotated[str, Field(alias="hybridDesc")]


class _Contract(BaseModel):
    start: str


class _SalaryType(BaseModel):
    period: str
    range: tuple[int, int]
    paid_holiday: Annotated[bool, Field(alias="paidHoliday")]


class _SalaryTypes(BaseModel):
    permanent: _SalaryType
    b2b: _SalaryType


class _Salary(BaseModel):
    currency: str
    types: _SalaryTypes
    disclosed_at: Annotated[str, Field(alias="disclosedAt")]


class _Essentials(BaseModel):
    contract: _Contract
    salary: Annotated[_Salary, Field(alias="originalSalary")]


class _Requirement(BaseModel):
    value: str
    type: str


class _Language(BaseModel):
    type: str
    code: str
    level: str | None = None


class _Requirements(BaseModel):
    musts: list[_Requirement]
    nices: list[_Requirement]
    description: str
    languages: list[_Language]


class _Posting(BaseModel):
    id: str
    title: str
    specs: _Specs
    company: _Company
    details: _Details
    location: _Location
    essentials: _Essentials
    requirements: _Requirements


class Client:
    def __init__(self) -> None:
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self) -> Self:
        self._client = await self._exit_stack.enter_async_context(
            httpx.AsyncClient(base_url="https://nofluffjobs.com")
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        return await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def get_posting(self, id: str) -> Posting:
        res = await self._client.get(f"pl/job/{id}")
        res.raise_for_status()

        tree = HTMLParser(res.text)
        state = tree.css_first("#serverApp-state")
        if not state:
            raise ValueError("State not found")

        raw: dict[str, Any] = json.loads(state.text())
        posting_key = next(key for key in raw if key.startswith("/posting/"))
        posting = _Posting.model_validate(raw[posting_key], by_alias=True)

        return {
            "title": posting.title,
            "description": posting.details.description,
            "skills": [
                *(
                    {"name": req.value, "optional": False, "level": None}
                    for req in posting.requirements.musts
                ),
                *(
                    {"name": req.value, "optional": True, "level": None}
                    for req in posting.requirements.nices
                ),
                *(
                    {
                        "name": lang.code,
                        "optional": lang.type != "MUST",
                        "level": lang.level,
                    }
                    for lang in posting.requirements.languages
                ),
            ],
        }
