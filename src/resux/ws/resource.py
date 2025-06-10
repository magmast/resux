from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from resux.util.form import FormField


class User(BaseModel):
    name: Annotated[str | None, FormField("What's your name?")] = None
    headline: Annotated[str | None, FormField("Headline")] = None
    email: Annotated[str | None, FormField("What's your email?")] = None
    website: Annotated[str | None, FormField("What's your website URL?")] = None
    phone: Annotated[str | None, FormField("What's your phone number?")] = None
    location: Annotated[str | None, FormField("Where are you located?")] = None
    description: Annotated[str, Field(alias="content"), FormField(skip=True)] = ""


class BaseResource(BaseModel):
    id: Annotated[str, Field(exclude=True)]


class Project(BaseResource):
    model_config = ConfigDict(validate_by_name=True)

    last_major_activity: datetime
    tags: list[str] = []
    stars: int
    summary: Annotated[str, Field(alias="content")]


class Profile(BaseResource):
    network: str
    username: str
    website: str
    icon: str
    content: str = ""
