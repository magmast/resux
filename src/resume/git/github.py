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
from github.Tag import Tag as RawTag
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
        get_by_key: Callable[[str], Awaitable[_TModel]] | None = None,
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

    @cached_property
    def _list(self) -> RawPagination[_TRaw]:
        return self.init()

    @override
    async def get(self, key: int | str) -> _TModel:
        match key:
            case int():
                raw = await asyncio.to_thread(self._list.__getitem__, key)
            case str() if self.get_by_key:
                raw = await self.get_by_key(key)
            case _:
                raise TypeError("Indexing by str is not supported for this model")

        return self.model_type.from_raw(raw)

    @override
    async def slice(self, start: int, stop: int) -> list[_TModel]:
        raws = await asyncio.to_thread(self._list.__getitem__, slice(start, stop))
        return [self.model_type.from_raw(raw) for raw in raws]

    @override
    async def all(self) -> list[_TModel]:
        raws = await asyncio.to_thread(self._list.__getitem__, slice(len(self)))
        return [self.model_type.from_raw(raw) for raw in raws]


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

    @override
    async def get_readme(self) -> File | None:
        try:
            file = await asyncio.to_thread(self.raw.get_readme)
            return File(file)
        except UnknownObjectException as e:
            if e.status == 404:
                return None
            raise

    @override
    async def get_files(self) -> AsyncIterator[File]:
        paths = [""]
        while paths:
            files = await asyncio.to_thread(self.raw.get_dir_contents, paths.pop())
            paths.extend((file.path for file in files if file.type == "dir"))
            for file in filter(lambda file: file.type == "file", files):
                yield File(file)

    @property
    @override
    def commits(self) -> Pagination[git.Commit]:
        async def _get_commit(sha: str) -> Commit:
            raw = await asyncio.to_thread(self.raw.get_commit, sha)
            return Commit(raw)

        return cast(
            Pagination[git.Commit],
            _PaginationAdapter(
                init=self.raw.get_commits,
                model_type=Commit,
                get_by_key=_get_commit,
            ),
        )

    @property
    @override
    def tags(self) -> Pagination[git.Tag]:
        return cast(
            Pagination[git.Tag],
            _PaginationAdapter(
                init=self.raw.get_tags,
                model_type=Tag,
            ),
        )

    @property
    @override
    def stars(self) -> int:
        return self.raw.stargazers_count


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
        async def _get_repo(key: str) -> Repo:
            raw = await asyncio.to_thread(self.raw.get_repo, key)
            return Repo(raw)

        return cast(
            Pagination[git.Repo],
            _PaginationAdapter(
                init=self.raw.get_repos,
                model_type=Repo,
                get_by_key=_get_repo,
            ),
        )


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


class Tag(git.Tag, _Model[RawTag]):
    def __init__(self, raw: RawTag) -> None:
        self.raw = raw

    @classmethod
    @override
    def from_raw(cls, raw: RawTag) -> Tag:
        return cls(raw)

    @property
    @override
    def name(self) -> str:
        return self.raw.name


class Client(git.Hub):
    def __init__(self, access_token: SecretStr) -> None:
        self._github = Github(access_token.get_secret_value())

    @override
    async def get_user(self) -> User:
        user = await asyncio.to_thread(self._github.get_user)
        return User(user)

    @property
    @override
    def repos(self) -> Pagination[git.Repo]:
        async def _get_repo(key: str) -> Repo:
            raw = await asyncio.to_thread(self._github.get_repo, key)
            return Repo(raw)

        return cast(
            Pagination[git.Repo],
            _PaginationAdapter(
                init=self._github.get_repos,
                model_type=Repo,
                get_by_key=_get_repo,
            ),
        )
