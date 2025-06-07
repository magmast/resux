import asyncio
from datetime import datetime
from typing import (
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Generic,
    Iterable,
    Protocol,
    Sized,
    TypeVar,
    overload,
)


T = TypeVar("T")


class Paginable(Sized, Iterable[T], Protocol):
    @overload
    def __getitem__(self, key: int | str) -> T: ...

    @overload
    def __getitem__(self, key: slice) -> list[T]: ...

    def __getitem__(self, key: int | str | slice) -> T | list[T]: ...


class AsyncPaginable(Sized, AsyncIterable[T], Protocol):
    @overload
    def __getitem__(self, key: int | str) -> Awaitable[T]: ...

    @overload
    def __getitem__(self, key: slice) -> Awaitable[list[T]]: ...

    def __getitem__(self, key: int | str | slice) -> Awaitable[T | list[T]]: ...


class AsyncPaginableAdapter(Generic[T]):
    def __init__(self, paginable: Paginable[T]) -> None:
        self._paginable = paginable

    def __len__(self) -> int:
        return len(self._paginable)

    @overload
    def __getitem__(self, key: int | str) -> Awaitable[T]: ...

    @overload
    def __getitem__(self, key: slice) -> Awaitable[list[T]]: ...

    def __getitem__(self, key: int | str | slice) -> Awaitable[T | list[T]]:
        return asyncio.to_thread(lambda: self._paginable[key])

    async def __aiter__(self) -> AsyncIterator[T]:
        i = iter(self._paginable)
        while True:
            item = await asyncio.to_thread(next, i, None)
            if item is None:
                break
            yield item


class User(Protocol):
    @property
    def email(self) -> str | None: ...

    @property
    def login(self) -> str: ...

    @property
    def name(self) -> str | None: ...

    @property
    def repos(self) -> AsyncPaginable["Repo"]: ...


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
    async def readme(self) -> File | None: ...

    @property
    def files(self) -> AsyncIterator[File]: ...

    @property
    def commits(self) -> AsyncPaginable[Commit]: ...


class Hub(Protocol):
    @property
    async def user(self) -> User: ...

    @property
    def repos(self) -> AsyncPaginable[Repo]: ...
