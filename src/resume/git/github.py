from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
from functools import cached_property
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Self,
    TypeVar,
    cast,
    overload,
    override,
)

from github import Github, UnknownObjectException
from github.AuthenticatedUser import AuthenticatedUser as RawAuthUser
from github.Commit import Commit as RawCommit
from github.ContentFile import ContentFile as RawFile
from github.GithubObject import GithubObject as RawObject
from github.NamedUser import NamedUser as RawNamedUser
from github.PaginatedList import PaginatedList as RawPagination
from github.Repository import Repository as RawRepository
from pydantic import SecretStr

from resume import git
from resume.git import Pagination


_TRaw = TypeVar("_TRaw", bound=RawObject)


class _Model(ABC, Generic[_TRaw]):
    @classmethod
    @abstractmethod
    def from_raw(cls, raw: _TRaw) -> Self: ...


_TModel = TypeVar("_TModel", bound=_Model)


class _PaginationAdapter(Pagination[_TModel], Generic[_TRaw, _TModel]):
    def __init__(
        self,
        *,
        init: Callable[[], RawPagination[_TRaw]],
        model_type: type[_TModel],
        get_by_key: Callable[[str], Awaitable[_TModel]],
    ) -> None:
        self.init = init
        self.model_type = model_type
        self.get_by_key = get_by_key

    @override
    def __len__(self) -> int:
        return self._list.totalCount

    @override
    async def __aiter__(self) -> AsyncIterator[_TModel]:
        items = iter(self._list)
        while raw := await asyncio.to_thread(next, items, None):
            yield self.model_type.from_raw(raw)

    @overload
    def __getitem__(self, key: int | str) -> Awaitable[_TModel]: ...

    @overload
    def __getitem__(
        self, key: slice[int | None, int, None]
    ) -> Awaitable[list[_TModel]]: ...

    @override
    def __getitem__(
        self,
        key: int | str | slice[int | None, int, None],
    ) -> Awaitable[_TModel | list[_TModel]]:
        match key:
            case int():
                return self._get_by_index(key)
            case str():
                return self.get_by_key(key)
            case slice():
                return self._get_by_slice(key)

    @cached_property
    def _list(self) -> RawPagination[_TRaw]:
        return self.init()

    async def _get_by_index(self, index: int) -> _TModel:
        raw = await asyncio.to_thread(self._list.__getitem__, index)
        return self.model_type.from_raw(raw)

    async def _get_by_slice(self, s: slice[int | None, int, None]) -> list[_TModel]:
        items = await asyncio.to_thread(self._list.__getitem__, s)
        return [self.model_type.from_raw(raw) for raw in items]


class Repo(git.Repo, _Model[RawRepository]):
    def __init__(self, raw: RawRepository) -> None:
        self.raw = raw

    @classmethod
    @override
    def from_raw(cls, raw: RawRepository) -> Repo:
        return cls(raw)

    @property
    @override
    def owner(self) -> User:
        return User(self.raw.owner)

    @property
    @override
    def name(self) -> str:
        return self.raw.name

    @property
    @override
    def full_name(self) -> str:
        return self.raw.full_name

    @property
    @override
    def description(self) -> str | None:
        return self.raw.description

    @property
    @override
    def readme(self) -> Awaitable[File | None]:
        return self._get_readme()

    async def _get_readme(self) -> File | None:
        try:
            file = await asyncio.to_thread(self.raw.get_readme)
            return File(file)
        except UnknownObjectException as e:
            if e.status == 404:
                return None
            raise

    @property
    @override
    def files(self) -> AsyncIterator[File]:
        return self._get_files()

    async def _get_files(self) -> AsyncIterator[File]:
        paths = [""]
        while paths:
            files = await asyncio.to_thread(self.raw.get_dir_contents, paths.pop())
            paths.extend((file.path for file in files if file.type == "dir"))
            for file in filter(lambda file: file.type == "file", files):
                yield File(file)

    @property
    @override
    def commits(self) -> Pagination[git.Commit]:
        return cast(
            Pagination[git.Commit],
            _PaginationAdapter(
                init=self.raw.get_commits,
                model_type=Commit,
                get_by_key=self._get_commit,
            ),
        )

    async def _get_commit(self, sha: str) -> Commit:
        raw = await asyncio.to_thread(self.raw.get_commit, sha)
        return Commit(raw)


class User(git.User, _Model[RawAuthUser | RawNamedUser]):
    def __init__(self, raw: RawNamedUser | RawAuthUser) -> None:
        self.raw = raw

    @classmethod
    @override
    def from_raw(cls, raw: RawNamedUser | RawAuthUser) -> User:
        return cls(raw)

    @property
    def email(self) -> str | None:
        return self.raw.email

    @property
    def login(self) -> str:
        return self.raw.login

    @property
    def name(self) -> str | None:
        return self.raw.name

    @property
    def repos(self) -> Pagination[git.Repo]:
        return cast(
            Pagination[git.Repo],
            _PaginationAdapter(
                init=self.raw.get_repos,
                model_type=Repo,
                get_by_key=self._get_repo,
            ),
        )

    async def _get_repo(self, key: str) -> Repo:
        raw = await asyncio.to_thread(self.raw.get_repo, key)
        return Repo(raw)


class File(git.File):
    def __init__(self, file: RawFile) -> None:
        self._file = file

    @property
    def path(self) -> str:
        return self._file.path

    @property
    def content(self) -> bytes:
        return self._file.decoded_content


class Commit(git.Commit, _Model[RawCommit]):
    def __init__(self, raw: RawCommit) -> None:
        self.raw = raw

    @classmethod
    @override
    def from_raw(cls, raw: RawCommit) -> Commit:
        return cls(raw)

    @property
    def sha(self) -> str:
        return self.raw.sha

    @property
    def message(self) -> str:
        return self.raw.commit.message

    @property
    def author(self) -> git.CommitAuthor:
        return self.raw.commit.author

    @property
    def author_date(self) -> datetime:
        return self.raw.commit.author.date


class Client(git.Hub):
    def __init__(self, access_token: SecretStr) -> None:
        self._github = Github(access_token.get_secret_value())

    @property
    @override
    def user(self) -> Awaitable[User]:
        return self._get_user()

    async def _get_user(self) -> User:
        user = await asyncio.to_thread(self._github.get_user)
        return User(user)

    @property
    @override
    def repos(self) -> Pagination[git.Repo]:
        return cast(
            Pagination[git.Repo],
            _PaginationAdapter(
                init=self._github.get_repos,
                model_type=Repo,
                get_by_key=self._get_repo,
            ),
        )

    async def _get_repo(self, key: str) -> Repo:
        raw = await asyncio.to_thread(self._github.get_repo, key)
        return Repo(raw)
