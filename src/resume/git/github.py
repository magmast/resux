import asyncio
from datetime import datetime
from typing import AsyncIterator, Callable, Generic, Iterator, TypeVar, cast, overload

from github import Github, UnknownObjectException
from github.AuthenticatedUser import AuthenticatedUser
from github.Commit import Commit as CommitObject
from github.ContentFile import ContentFile
from github.GithubObject import GithubObject
from github.NamedUser import NamedUser
from github.PaginatedList import PaginatedList
from github.Repository import Repository
from pydantic import SecretStr

from resume import git
from resume.git import AsyncPaginable, AsyncPaginableAdapter


TOriginal = TypeVar("TOriginal", bound=GithubObject)
TItem = TypeVar("TItem")


class PaginableAdapter(Generic[TOriginal, TItem]):
    def __init__(
        self,
        list: Callable[[], PaginatedList[TOriginal]],
        *,
        map: Callable[[TOriginal], TItem],
        by_key: Callable[[str], TOriginal] | None = None,
    ) -> None:
        self._create_list = list
        self._map = map
        self._by_key = by_key
        self._cached_list: PaginatedList[TOriginal] | None = None

    @property
    def _list(self) -> PaginatedList[TOriginal]:
        if self._cached_list is None:
            self._cached_list = self._create_list()
        return self._cached_list

    @overload
    def __getitem__(self, key: int | str) -> TItem: ...

    @overload
    def __getitem__(self, key: slice) -> list[TItem]: ...

    def __getitem__(self, key: int | str | slice) -> TItem | list[TItem]:
        if isinstance(key, int):
            return self._map(self._list[key])

        if isinstance(key, slice):
            return list(map(self._map, self._list[key]))

        if not self._by_key:
            raise TypeError("Invalid key type")

        try:
            return self._map(self._by_key(key))
        except KeyError:
            raise KeyError(key)

    def __len__(self) -> int:
        return self._list.totalCount

    def __iter__(self) -> Iterator[TItem]:
        return map(self._map, iter(self._list))

    def to_async(self) -> AsyncPaginable[TItem]:
        return AsyncPaginableAdapter(self)


class User(git.User):
    def __init__(self, user: NamedUser | AuthenticatedUser) -> None:
        self._user = user

    @property
    def email(self) -> str | None:
        return self._user.email

    @property
    def login(self) -> str:
        return self._user.login

    @property
    def name(self) -> str | None:
        return self._user.name

    @property
    def repos(self) -> AsyncPaginable["git.Repo"]:
        adapter = PaginableAdapter(
            self._user.get_repos,
            map=lambda repo: cast(git.Repo, Repo(repo)),
            by_key=lambda name: self._user.get_repo(name),
        )
        return adapter.to_async()


class File(git.File):
    def __init__(self, file: ContentFile) -> None:
        self._file = file

    @property
    def path(self) -> str:
        return self._file.path

    @property
    def content(self) -> bytes:
        return self._file.decoded_content


class Commit(git.Commit):
    def __init__(self, commit: CommitObject) -> None:
        self._commit = commit

    @property
    def sha(self) -> str:
        return self._commit.sha

    @property
    def message(self) -> str:
        return self._commit.commit.message

    @property
    def author(self) -> git.CommitAuthor:
        return self._commit.commit.author

    @property
    def author_date(self) -> datetime:
        return self._commit.commit.author.date


class Repo(git.Repo):
    def __init__(self, repo: Repository) -> None:
        self._repo = repo

    @property
    def owner(self) -> User:
        return User(self._repo.owner)

    @property
    def name(self) -> str:
        return self._repo.name

    @property
    def full_name(self) -> str:
        return self._repo.full_name

    @property
    def description(self) -> str | None:
        return self._repo.description

    @property
    async def readme(self) -> File | None:
        try:
            file = await asyncio.to_thread(self._repo.get_readme)
            return File(file)
        except UnknownObjectException as e:
            if e.status == 404:
                return None
            raise

    @property
    async def files(self) -> AsyncIterator[File]:
        paths = [""]
        while paths:
            files = await asyncio.to_thread(self._repo.get_dir_contents, paths.pop())
            paths.extend((file.path for file in files if file.type == "dir"))
            for file in filter(lambda file: file.type == "file", files):
                yield File(file)

    @property
    def commits(self) -> AsyncPaginable[git.Commit]:
        adapter = PaginableAdapter(
            self._repo.get_commits,
            map=lambda commit: cast(git.Commit, Commit(commit)),
            by_key=lambda sha: self._repo.get_commit(sha),
        )
        return adapter.to_async()


class Client(git.Hub):
    def __init__(self, access_token: SecretStr) -> None:
        self._client = Github(access_token.get_secret_value())

    @property
    async def user(self) -> User:
        user = await asyncio.to_thread(self._client.get_user)
        return User(user)

    @property
    def repos(self) -> AsyncPaginable[git.Repo]:
        adapter = PaginableAdapter(
            self._client.get_repos,
            map=lambda repo: cast(git.Repo, Repo(repo)),
            by_key=lambda full_name: self._client.get_repo(full_name),
        )
        return adapter.to_async()
