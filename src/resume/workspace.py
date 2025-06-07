import asyncio
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Generic,
    Protocol,
    TypeVar,
    override,
)

import aiofiles
from aiofiles import os
import frontmatter
from pydantic import BaseModel


class Resource(Protocol):
    @property
    def id(self) -> str: ...


T = TypeVar("T", bound=Resource)


class ResourceFormat(Protocol, Generic[T]):
    @property
    def ext(self) -> str: ...

    def load(self, id: str, data: bytes) -> T: ...

    def dump(self, resource: T) -> bytes: ...


class _Missing:
    @override
    def __repr__(self) -> str:
        return "<missing>"


class ResourceService(AsyncIterable[T]):
    def __init__(self, path: Path, *, format: ResourceFormat[T]) -> None:
        self.path = path
        self.format = format

        self._cache: dict[str, T | None | _Missing] = {}
        self._all_cached = False

    @override
    async def __aiter__(self) -> AsyncIterator[T]:
        resources: list[asyncio.Task[T]] = []
        async for id in self.ids:
            resources.append(asyncio.create_task(self.get(id)))

        for resource in asyncio.as_completed(resources):
            yield await resource

    @property
    def ids(self) -> AsyncIterator[str]:
        return self._get_ids()

    async def _get_ids(self) -> AsyncIterator[str]:
        await self._cache_missing_ids()
        for id in self._cache:
            yield id

    @property
    def size(self) -> Awaitable[int]:
        return self._get_size()

    async def _get_size(self) -> int:
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
        try:
            path = self._get_path(id)
            async with aiofiles.open(path, "rb") as f:
                data = await f.read()
            return self.format.load(id, data)
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
        return self.path / id

    def _get_id(self, path: str) -> str:
        rel = Path(path).relative_to(self.path)
        return "/".join(rel.parts)


class Project(BaseModel):
    id: str
    last_major_activity: datetime
    tags: list[str] = []
    summary: str


class MarkdownProjectFormat(ResourceFormat[Project]):
    """Markdown format for projects"""

    @property
    @override
    def ext(self) -> str:
        return ".md"

    @override
    def load(self, id: str, data: bytes) -> Project:
        post = frontmatter.load(data.decode())
        return Project.model_validate(
            {
                **post.metadata,
                "id": id,
                "summary": post.content,
            }
        )

    @override
    def dump(self, resource: Project) -> bytes:
        from frontmatter import Post

        metadata = resource.model_dump()
        content = metadata.pop("summary")
        post = Post(content, **metadata)
        return frontmatter.dumps(post).encode()


class Workspace:
    def __init__(
        self,
        path: Path = Path(),
        *,
        project_format: ResourceFormat[Project] = MarkdownProjectFormat(),
    ) -> None:
        self.path = path
        self.projects = ResourceService(self.path / "projects", format=project_format)
