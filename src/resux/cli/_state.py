import asyncio
from functools import cache
from pathlib import Path
from typing import Annotated, override

import logfire
import typer

from resux import ai
from resux.git import github as gh
from resux.ws import Workspace


_workspace: Workspace | None = None


def callback(
    workspace_path: Annotated[
        Path | None,
        typer.Option("--workspace", help="Path to the workspace directory."),
    ] = None,
) -> None:
    global _workspace

    async def resolve_workspace() -> Path | None:
        return await Workspace.find_path() if workspace_path is None else workspace_path

    workspace_path = asyncio.run(resolve_workspace())
    if workspace_path is None:
        return

    _workspace = Workspace(workspace_path)
    ai.init(_workspace.env.openrouter_api_key)

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


@cache
def github() -> gh.Client:
    return gh.Client(workspace().env.github_access_token)
