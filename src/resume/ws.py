from __future__ import annotations

import asyncio
from datetime import datetime
from glob import glob
from pathlib import Path
import shutil
from typing import (
    Annotated,
    AsyncIterable,
    AsyncIterator,
    NotRequired,
    Protocol,
    TypeVar,
    TypedDict,
    Unpack,
    override,
)

import aiofiles
from aiofiles import os
import frontmatter
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic_settings import BaseSettings

from resume.form import FormField


MANIFEST_FILENAME = "resume.toml"
ENV_FILENAME = ".env"


class BaseResource(BaseModel):
    id: Annotated[str, Field(exclude=True)]


T = TypeVar("T", bound=BaseResource)


class ResourceFormat(Protocol):
    @property
    def ext(self) -> str: ...

    def load(self, id: str, data: bytes, resource_type: type[T]) -> T: ...

    def dump(
        self,
        resource: BaseModel,
        *,
        exclude_none: bool = False,
        exclude_defaults: bool = False,
    ) -> bytes: ...


class MarkdownResourceFormat(ResourceFormat):
    """Markdown format for projects"""

    @property
    @override
    def ext(self) -> str:
        return ".md"

    @override
    def load(self, id: str, data: bytes, resource_type: type[T]) -> T:
        post = frontmatter.loads(data.decode())
        return resource_type.model_validate(
            {**post.metadata, "id": id, "content": post.content},
            by_alias=True,
        )

    @override
    def dump(
        self,
        resource: BaseModel,
        *,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> bytes:
        from frontmatter import Post

        metadata = resource.model_dump(
            by_alias=True,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        content = metadata.pop("content")
        post = Post(content, **metadata)
        return frontmatter.dumps(post).encode()


class _Missing:
    @override
    def __repr__(self) -> str:
        return "<missing>"


class ResourceService(AsyncIterable[T]):
    def __init__(
        self,
        path: Path,
        *,
        resource_type: type[T],
        format: ResourceFormat = MarkdownResourceFormat(),
    ) -> None:
        self.path = path
        self.resource_type = resource_type
        self.format = format

        self._cache: dict[str, T | None | _Missing] = {}
        self._all_cached = False

    @override
    async def __aiter__(self) -> AsyncIterator[T]:
        resources: list[asyncio.Task[T]] = []
        for id in await self.ids():
            resources.append(asyncio.create_task(self.get(id)))

        for resource in asyncio.as_completed(resources):
            yield await resource

    async def ids(self) -> list[str]:
        await self._cache_missing_ids()
        return list(self._cache)

    async def size(self) -> int:
        await self._cache_missing_ids()
        return sum(
            1 for value in self._cache.values() if not isinstance(value, _Missing)
        )

    async def contains(self, id: str) -> bool:
        resource = self._cache.get(id)
        if resource is None:
            exists = await os.path.exists(self._get_path(id))
            resource = None if exists else _Missing()
            self._cache[id] = resource
        return not isinstance(resource, _Missing)

    async def get(self, id: str) -> T:
        resource = self._cache.get(id)
        if resource is None:
            resource = await self._get_or_missing(id)
            self._cache[id] = resource

        if isinstance(resource, _Missing):
            raise KeyError(id)

        return resource

    async def _get_or_missing(self, id: str) -> T | _Missing:
        path = self._get_path(id)
        try:
            async with aiofiles.open(path, "rb") as f:
                data = await f.read()
            return self.format.load(id, data, resource_type=self.resource_type)
        except FileNotFoundError:
            return _Missing()

    async def set(self, resource: T) -> None:
        path = self._get_path(resource.id)
        await os.makedirs(path.parent, exist_ok=True)

        data = self.format.dump(resource)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

    async def delete(self, id: str) -> None:
        path = self._get_path(id)
        try:
            await os.remove(path)
            siblings = await os.listdir(path.parent)
            if len(siblings) == 0:
                await os.rmdir(path.parent)
        except FileNotFoundError:
            raise KeyError(id)

    async def _cache_missing_ids(self) -> None:
        if self._all_cached:
            return

        paths = await asyncio.to_thread(
            glob,
            f"**/*{self.format.ext}",
            root_dir=self.path,
        )
        all_ids = {self._get_id(path) for path in paths}

        deleted_ids = (id for id in self._cache if id not in all_ids)
        for id in deleted_ids:
            self._cache[id] = _Missing()

        added_ids = (id for id in all_ids if id not in self._cache)
        for id in added_ids:
            self._cache[id] = None

        self._all_cached = True

    def _get_path(self, id: str) -> Path:
        return self.path / f"{id}{self.format.ext}"

    def _get_id(self, path: str) -> str:
        return "/".join(Path(path).with_suffix("").parts)


class User(BaseModel):
    name: Annotated[str | None, FormField("What's your name?")] = None
    headline: Annotated[str | None, FormField("Headline")] = None
    email: Annotated[str | None, FormField("What's your email?")] = None
    website: Annotated[str | None, FormField("What's your website URL?")] = None
    phone: Annotated[str | None, FormField("What's your phone number?")] = None
    location: Annotated[str | None, FormField("Where are you located?")] = None
    description: Annotated[str, Field(alias="content"), FormField(skip=True)] = ""


class Project(BaseResource):
    model_config = ConfigDict(validate_by_name=True)

    last_major_activity: datetime
    tags: list[str] = []
    stars: int
    summary: Annotated[str, Field(alias="content")]


class Environment(BaseSettings):
    logfire: Annotated[bool, FormField("Enable logfire?")] = False
    openrouter_api_key: Annotated[SecretStr, Field(title="OpenRouter API key")]
    github_access_token: Annotated[SecretStr, Field(title="GitHub access token")]


class BaseWorkspaceKwargs(TypedDict, total=False):
    format: ResourceFormat


class WorkspaceKwargs(BaseWorkspaceKwargs, total=False):
    environment: Environment


class InitWorkspaceKwargs(BaseWorkspaceKwargs):
    override: NotRequired[bool]
    environment: Environment
    user: User


class Workspace:
    def __init__(self, path: Path, **kwargs: Unpack[WorkspaceKwargs]) -> None:
        self.path = path
        self.environment = kwargs.get("environment") or Environment(
            _env_file=self.path / ENV_FILENAME  # type: ignore
        )
        self.format = kwargs.get("format") or MarkdownResourceFormat()
        self.projects = ResourceService(
            self.path / "projects",
            resource_type=Project,
            format=self.format,
        )

    @staticmethod
    async def init(path: Path, **kwargs: Unpack[InitWorkspaceKwargs]) -> Workspace:
        """Initializes the workspace."""

        initializer = _WorkspaceInitializer(path)
        return await initializer(**kwargs)

    async def set_user(self, user: User) -> None:
        async with aiofiles.open(self.path / f"about-me{self.format.ext}", "wb") as f:
            await f.write(self.format.dump(user, exclude_none=True))


class _WorkspaceInitializer:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def __call__(self, **kwargs: Unpack[InitWorkspaceKwargs]) -> Workspace:
        """Initializes the workspace."""

        await self._init_root(override=kwargs.get("override", False))
        await asyncio.gather(
            asyncio.to_thread((self.path / MANIFEST_FILENAME).touch),
            self._init_env(kwargs["environment"]),
            self._init_env_example(kwargs["environment"]),
        )

        ws = Workspace(self.path, **kwargs)
        await ws.set_user(kwargs["user"])

        return ws

    async def _init_root(self, *, override: bool) -> None:
        try:
            await os.makedirs(self.path)
        except FileExistsError:
            if not await self._is_empty_dir() and not override:
                raise

            await asyncio.to_thread(shutil.rmtree, self.path)
            await os.mkdir(self.path)

    async def _is_empty_dir(self) -> bool:
        try:
            children = await os.listdir(self.path)
            return len(children) == 0
        except NotADirectoryError:
            return False

    async def _init_env(self, env: Environment) -> None:
        async with aiofiles.open(self.path / ENV_FILENAME, "w") as f:
            for key, raw in env.model_dump().items():
                match raw:
                    case SecretStr():
                        value = f'"{raw.get_secret_value()}"'
                    case str():
                        value = f'"{raw}"'
                    case bool():
                        value = str(raw).lower()
                    case _:
                        raise ValueError(f"Unsupported type: {type(raw)}")
                await f.write(f"{key.upper()}={value}\n")

    async def _init_env_example(self, env: Environment) -> None:
        async with aiofiles.open(self.path / f"{ENV_FILENAME}.example", "w") as f:
            for key in env.model_dump().keys():
                await f.write(f"{key.upper()}=\n")
