from __future__ import annotations

from datetime import datetime
from typing import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Protocol,
    Sized,
    TypeVar,
    overload,
)


T = TypeVar("T")


class Pagination(Sized, AsyncIterable[T], Protocol):
    @overload
    def __getitem__(self, key: int | str) -> Awaitable[T]: ...

    @overload
    def __getitem__(
        self, key: slice[int | None, int | None, None]
    ) -> Awaitable[list[T]]: ...

    def __getitem__(
        self,
        key: int | str | slice[int | None, int | None, None],
    ) -> Awaitable[T | list[T]]: ...


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

    @property
    def readme(self) -> Awaitable[File | None]: ...

    @property
    def files(self) -> AsyncIterator[File]: ...

    @property
    def commits(self) -> Pagination[Commit]: ...

    @property
    def tags(self) -> Pagination[Tag]: ...

    @property
    def stars(self) -> int: ...


class Hub(Protocol):
    @property
    def user(self) -> Awaitable[User]: ...

    @property
    def repos(self) -> Pagination[Repo]: ...
