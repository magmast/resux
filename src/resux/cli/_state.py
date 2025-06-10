import asyncio
import functools
from pathlib import Path
from typing import Annotated, Awaitable, override

import logfire
from pydantic_ai.providers.openrouter import OpenRouterProvider
import typer

from resux.ai.core import LazyOpenRouterModel
from resux.git import github as gh
from resux.ws import Workspace


_workspace: Workspace | None = None


def callback(
    workspace_path: Annotated[
        Path | None | Awaitable[Path | None],
        typer.Option("--workspace", help="Path to the workspace directory."),
    ] = Workspace.find_path(),
) -> None:
    global _workspace

    async def resolve_workspace() -> Path | None:
        return (
            await workspace_path
            if isinstance(workspace_path, Awaitable)
            else workspace_path
        )

    workspace_path = asyncio.run(resolve_workspace())
    if workspace_path is None:
        return

    _workspace = Workspace(workspace_path)

    LazyOpenRouterModel.set_provider(
        OpenRouterProvider(api_key=_workspace.env.openrouter_api_key.get_secret_value())
    )

    if _workspace.env.logfire:
        logfire.configure()
        logfire.instrument_pydantic_ai()


def workspace() -> Workspace:
    if _workspace is None:
        raise NotInWorkspaceError()
    return _workspace


class NotInWorkspaceError(Exception):
    @override
    def __str__(self) -> str:
        return "Workspace not found"


@functools.cache
def github() -> gh.Client:
    return gh.Client(workspace().env.github_access_token)
