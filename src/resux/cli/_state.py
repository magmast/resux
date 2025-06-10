import functools
from pathlib import Path
from typing import Annotated, override

import logfire
from pydantic_ai.providers.openrouter import OpenRouterProvider
import typer

from resux import ws
from resux.ai.core import LazyOpenRouterModel
from resux.git import github as gh


_workspace: ws.Workspace | None = None


def callback(
    workspace: Annotated[
        Path | None,
        typer.Option(help="Path to the workspace directory."),
    ] = ws.find(),
) -> None:
    global _workspace
    if workspace is None:
        return

    _workspace = ws.Workspace(workspace)

    LazyOpenRouterModel.set_provider(
        OpenRouterProvider(
            api_key=_workspace.environment.openrouter_api_key.get_secret_value()
        )
    )

    if _workspace.environment.logfire:
        logfire.configure()
        logfire.instrument_pydantic_ai()


def workspace() -> ws.Workspace:
    if _workspace is None:
        raise NotInWorkspaceError()
    return _workspace


class NotInWorkspaceError(Exception):
    @override
    def __str__(self) -> str:
        return "Workspace not found"


@functools.cache
def github() -> gh.Client:
    return gh.Client(workspace().environment.github_access_token)
