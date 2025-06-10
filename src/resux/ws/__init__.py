from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
from typing import Annotated

import aiofiles
from aiofiles import os
from pydantic import SecretStr
from pydantic_settings import BaseSettings

from resux.util.form import FormField
from resux.ws.collection import ResourceCollection, ResourceSingleton
from resux.ws.format import MarkdownResourceFormat, ResourceFormat
from resux.ws.resource import Profile, Project, User


MANIFEST_FILENAME = "resux.toml"
ENV_FILENAME = ".env"


class Environment(BaseSettings):
    logfire: Annotated[bool, FormField("Enable logfire?")] = False
    openrouter_api_key: Annotated[SecretStr, FormField("OpenRouter API key")]
    github_access_token: Annotated[SecretStr, FormField("GitHub access token")]

    @classmethod
    def from_dotenv(cls, path: Path | str) -> Environment:
        return cls(_env_file=Path(path) / ENV_FILENAME)  # type: ignore


class Workspace:
    def __init__(
        self,
        path: Path | str,
        *,
        env: Environment | None = None,
        format: ResourceFormat = MarkdownResourceFormat(),
    ) -> None:
        self.path = Path(path)
        self.env = env or Environment.from_dotenv(self.path)
        self.projects = ResourceCollection(
            Project,
            self.path / "projects",
            format=format,
        )
        self.profiles = ResourceCollection(
            Profile,
            self.path / "profiles",
            format=format,
        )
        self.user = ResourceSingleton(User, self.path, "about-me", format=format)

    @staticmethod
    async def init(
        path: Path | str,
        *,
        override: bool = False,
        format: ResourceFormat = MarkdownResourceFormat(),
        env: Environment,
        user: User | None = None,
    ) -> Workspace:
        initializer = _Initializer(path)
        return await initializer(
            override=override,
            format=format,
            env=env,
            user=user,
        )

    @staticmethod
    async def find_path(start: Path | str = Path.cwd()) -> Path | None:
        start = Path(start)
        search = (
            start,
            *start.parents,
            start / "resume",
        )

        for path in search:
            if Workspace.is_workspace(path):
                return path

    @staticmethod
    def is_workspace(path: Path | str) -> bool:
        path = Path(path)
        return (path / MANIFEST_FILENAME).exists()


class _Initializer:
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self.path = Path(path)

    async def __call__(
        self,
        *,
        override: bool,
        format: ResourceFormat,
        env: Environment,
        user: User | None,
    ) -> Workspace:
        await self._init_root(override=override)
        await asyncio.gather(
            asyncio.to_thread((self.path / MANIFEST_FILENAME).touch),
            self._init_env(env),
            self._init_env_example(env),
            self._init_gitignore(),
        )

        ws = Workspace(self.path, env=env)
        if user:
            await ws.user.set(user)

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

    async def _init_gitignore(self) -> None:
        async with aiofiles.open(self.path / ".gitignore", "w") as f:
            await f.write(".env")
