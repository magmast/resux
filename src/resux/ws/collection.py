from __future__ import annotations

import asyncio
from glob import glob
from pathlib import Path
import shutil
from typing import AsyncIterator, Generic, TypeVar

import aiofiles
from aiofiles import os
from pydantic import BaseModel

from resux.ws.format import MarkdownResourceFormat, ResourceFormat
from resux.ws.resource import BaseResource


TRes = TypeVar("TRes", bound=BaseResource)


class _Missing:
    pass


_MISSING = _Missing()


class ResourceCollection(Generic[TRes]):
    def __init__(
        self,
        type: type[TRes],
        path: Path | str,
        *,
        format: ResourceFormat = MarkdownResourceFormat(),
    ) -> None:
        self.path = Path(path)
        self.type = type
        self.format = format
        self._cache: dict[str, TRes | _Missing | None] = {}
        self._all_cached = False

    async def __aiter__(self) -> AsyncIterator[TRes]:
        ids = await asyncio.to_thread(self.get_ids)
        resources = [asyncio.create_task(self.get(id)) for id in ids]
        for resource in asyncio.as_completed(resources):
            yield await resource

    def get_size(self) -> int:
        return len(self.get_ids())

    def get_ids(self) -> list[str]:
        self._cache_missing_ids()
        return list(
            id for id, value in self._cache.items() if not isinstance(value, _Missing)
        )

    def _cache_missing_ids(self) -> None:
        if self._all_cached:
            return

        paths = glob(f"**/*{self.format.ext}", root_dir=self.path, recursive=True)
        ids = {self._get_id(path) for path in paths}

        to_delete = (id for id in self._cache if id not in ids)
        for id in to_delete:
            self._cache[id] = _MISSING

        to_add = (id for id in ids if id not in self._cache)
        for id in to_add:
            self._cache[id] = None

        self._all_cached = True

    def _get_id(self, path: Path | str) -> str:
        return str(Path(path).absolute().relative_to(self.path).with_suffix(""))

    async def contains(self, id: str) -> bool:
        try:
            resource = self._cache[id]
            return not isinstance(resource, _Missing)
        except KeyError:
            path = self._get_path(id)
            exists = path.exists()
            self._cache[id] = None if exists else _MISSING
            return exists

    async def get(self, id: str) -> TRes:
        resource = self._cache.get(id)

        if resource is None:
            resource = await self._read(id)
            self._cache[id] = resource

        if isinstance(resource, _Missing):
            raise KeyError(id)

        return resource

    async def _read(self, id: str) -> TRes | _Missing:
        try:
            path = self._get_path(id)
            async with aiofiles.open(path, "rb") as f:
                data = await f.read()
            return self.format.load(self.type, data, defaults={"id": id})
        except FileNotFoundError:
            return _MISSING

    def _get_path(self, id: str) -> Path:
        return self.path / f"{id}{self.format.ext}"

    async def set(self, resource: TRes) -> None:
        path = self._get_path(resource.id)
        await os.makedirs(path.parent, exist_ok=True)

        data = self.format.dump(resource)
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)

    async def delete(self, id: str) -> None:
        try:
            path = self._get_path(id)
            await os.remove(path)

            await self._delete_empty(path)
        except FileNotFoundError as e:
            raise KeyError(id) from e

    async def _delete_empty(self, path: Path | str) -> None:
        path = Path(path).absolute().relative_to(self.path)
        deepest: Path | None = None
        while path != path.parent:
            entries = await os.listdir(path)
            if entries:
                break

            deepest = path
            path = path.parent

        if deepest:
            await asyncio.to_thread(shutil.rmtree, deepest)


TModel = TypeVar("TModel", bound=BaseModel)


class ResourceSingleton(Generic[TModel]):
    def __init__(
        self,
        type: type[TModel],
        dir: Path | str,
        id: str,
        *,
        format: ResourceFormat = MarkdownResourceFormat(),
    ) -> None:
        self.type = type
        self.dir = dir
        self.id = id
        self.format = format

    @property
    def _path(self) -> Path:
        return Path(self.dir) / f"{self.id}{self.format.ext}"

    def exists(self) -> bool:
        return self._path.exists()

    async def get(self) -> TModel:
        try:
            async with aiofiles.open(self._path, "rb") as f:
                return self.format.load(self.type, await f.read())
        except FileNotFoundError:
            raise KeyError(self.id)

    async def set(self, resource: TModel) -> None:
        async with aiofiles.open(self._path, "wb") as f:
            await f.write(self.format.dump(resource))

    async def delete(self) -> None:
        try:
            await os.remove(self._path)
        except FileNotFoundError:
            raise KeyError(self.id)
