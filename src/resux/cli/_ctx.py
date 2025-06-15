import asyncio
from dataclasses import dataclass
from functools import cached_property
import inspect
from pathlib import Path
from typing import Annotated, Callable, Concatenate, ParamSpec, TypeVar, override

from makefun import wraps
import logfire
import typer

from resux import ai
from resux.git import github as gh
from resux.ws import Workspace


@dataclass
class Context:
    _workspace: Workspace | None = None

    @property
    def workspace(self):
        if self._workspace is None:
            raise NotInWorkspaceError()
        return self._workspace

    @cached_property
    def github(self):
        return gh.Client(self.workspace.env.github_access_token)


class NotInWorkspaceError(Exception):
    @override
    def __str__(self) -> str:
        return "Workspace not found"


_context = Context()


def _scrubbing_callback(m: logfire.ScrubMatch):
    if (
        m.path == ("attributes", "all_messages_events", 1, "content")
        and m.pattern_match.group(0) == "auth"
    ):
        return m.value


def callback(
    workspace_path: Annotated[
        Path | None,
        typer.Option("--workspace", help="Path to the workspace directory."),
    ] = None,
) -> None:
    global _context

    async def resolve_workspace() -> Path | None:
        return await Workspace.find_path() if workspace_path is None else workspace_path

    workspace_path = asyncio.run(resolve_workspace())
    if workspace_path is None:
        return

    _context._workspace = Workspace(workspace_path)
    ai.init(_context.workspace.env.openrouter_api_key)

    if _context.workspace.env.logfire:
        logfire.configure(scrubbing=logfire.ScrubbingOptions(_scrubbing_callback))
        logfire.instrument_pydantic_ai()


P = ParamSpec("P")
T = TypeVar("T")


def contextual(fn: Callable[Concatenate[Context, P], T]) -> Callable[P, T]:
    sig = inspect.signature(fn)

    ctx_param_item = next(iter(sig.parameters.items()), None)
    if ctx_param_item is None:
        raise TypeError("First parameter of a contextual function must be Context")

    ctx_key, ctx_param = ctx_param_item
    if ctx_key is None or ctx_param.annotation is not Context:
        raise TypeError("First parameter of a contextual function must be Context")

    @wraps(fn, remove_args=ctx_key)  # type: ignore
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return fn(_context, *args, **kwargs)

    return wrapper
