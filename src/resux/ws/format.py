from typing import Any, Protocol, TypeVar, override

import frontmatter
from frontmatter import Post
from pydantic import BaseModel


T = TypeVar("T", bound=BaseModel)


class ResourceFormat(Protocol):
    @property
    def ext(self) -> str: ...

    def load(
        self, type: type[T], data: bytes, *, defaults: dict[str, Any] = {}
    ) -> T: ...

    def dump(self, resource: BaseModel) -> bytes: ...


class MarkdownResourceFormat(ResourceFormat):
    @property
    @override
    def ext(self) -> str:
        return ".md"

    @override
    def load(self, type: type[T], data: bytes, *, defaults: dict[str, Any] = {}) -> T:
        post = frontmatter.loads(data.decode())
        return type(**defaults, **post.metadata, content=post.content)

    @override
    def dump(self, resource: BaseModel) -> bytes:
        metadata = resource.model_dump(by_alias=True)
        content = metadata.pop("content")
        post = Post(content, **metadata)
        return frontmatter.dumps(post).encode()
