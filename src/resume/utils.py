import asyncio
from datetime import datetime
from functools import wraps
from glob import glob
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    ParamSpec,
    TypeVar,
)

import aiofiles
import aiofiles.os as os
import frontmatter
from pydantic import BaseModel


class Unset:
    def __repr__(self) -> str:
        return "<unset>"


UNSET = Unset()


TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")


def asyncio_run(
    func: Callable[TParams, Coroutine[Any, Any, TReturn]],
) -> Callable[TParams, TReturn]:
    @wraps(func)
    def wrapper(*args: TParams.args, **kwargs: TParams.kwargs) -> TReturn:
        return asyncio.run(func(*args, **kwargs))

    return wrapper


class Project(BaseModel):
    id: str
    last_major_activity: datetime
    tags: list[str] = []
    summary: str


class Projects:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._cache: dict[str, Project] = {}
        self._all_cached: bool = False

    async def __aiter__(self) -> AsyncIterator[Project]:
        if self._all_cached:
            for project in self._cache.values():
                yield project
            return

        tasks = [asyncio.create_task(self.read(id)) async for id in self.ids]

        for task in asyncio.as_completed(tasks):
            yield await task

        self._all_cached = True

    @property
    async def ids(self) -> AsyncIterator[str]:
        if self._all_cached:
            for id in self._cache.keys():
                yield id
            return

        paths = await asyncio.to_thread(
            glob,
            "*/*.md",
            root_dir=self._path,
            recursive=True,
        )

        for path in paths:
            yield self._get_id(path)

    async def read(self, id: str) -> Project:
        try:
            path = self._get_path(id)
            async with aiofiles.open(path) as f:
                text = await f.read()
                metadata, summary = frontmatter.parse(text)

            project = Project.model_validate({**metadata, "id": id, "summary": summary})
            self._cache[id] = project

            return project
        except FileNotFoundError:
            raise KeyError(id)

    async def write(self, project: Project) -> None:
        path = self._get_path(project)

        await os.makedirs(path.parent, exist_ok=True)
        async with aiofiles.open(path, "w") as f:
            metadata = project.model_dump()
            content = metadata.pop("summary")
            post = frontmatter.Post(content, **metadata)
            text = frontmatter.dumps(post)
            await f.write(text)

        self._cache[project.id] = project

    async def adel(self, id: str) -> None:
        path = self._get_path(id)
        await os.remove(path)

        siblings = await os.listdir(path.parent)
        if len(siblings) == 0:
            await os.rmdir(path.parent)

    async def acontains(self, id: str) -> bool:
        if id in self._cache:
            return True
        elif self._all_cached:
            return False

        path = self._get_path(id)
        return await os.path.exists(path)

    def _get_path(self, id_or_project: str | Project) -> Path:
        id = id_or_project.id if isinstance(id_or_project, Project) else id_or_project
        return self._path / f"{id}.md"

    def _get_id(self, path: str | Path) -> str:
        path = Path(path)
        return f"{path.parent.name}/{path.stem}"


class Workspace:
    def __init__(self, path: Path = Path()) -> None:
        self._path = path
        self._projects = Projects(self._path / "projects")

    @property
    def projects(self) -> Projects:
        return self._projects
