from __future__ import annotations

from datetime import datetime
from typing import (
    AsyncIterable,
    AsyncIterator,
    Protocol,
    Sized,
    TypeVar,
)


T = TypeVar("T")


class Pagination(Sized, AsyncIterable[T], Protocol):
    async def get(self, key: int | str) -> T: ...

    async def slice(self, start: int, stop: int) -> list[T]: ...

    async def all(self) -> list[T]: ...


class User(Protocol):
    @property
    def email(self) -> str | None: ...

    @property
    def login(self) -> str: ...

    @property
    def name(self) -> str | None: ...

    @property
    def repos(self) -> Pagination[Repo]: ...


class File(Protocol):
    @property
    def path(self) -> str: ...

    @property
    def content(self) -> bytes: ...


class CommitAuthor(Protocol):
    @property
    def email(self) -> str: ...

    @property
    def name(self) -> str: ...


class Commit(Protocol):
    @property
    def sha(self) -> str: ...

    @property
    def message(self) -> str: ...

    @property
    def author(self) -> CommitAuthor: ...

    @property
    def author_date(self) -> datetime: ...


class Tag(Protocol):
    @property
    def name(self) -> str: ...


class Repo(Protocol):
    @property
    def owner(self) -> User: ...

    @property
    def name(self) -> str: ...

    @property
    def full_name(self) -> str: ...

    @property
    def description(self) -> str | None: ...

    async def get_readme(self) -> File | None: ...

    def get_files(self) -> AsyncIterator[File]: ...

    @property
    def commits(self) -> Pagination[Commit]: ...

    @property
    def tags(self) -> Pagination[Tag]: ...

    @property
    def stars(self) -> int: ...


class Hub(Protocol):
    async def get_user(self) -> User: ...

    @property
    def repos(self) -> Pagination[Repo]: ...
