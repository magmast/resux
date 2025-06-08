import functools
import os
from pathlib import Path
from typing import Annotated, override

import logfire
import typer

from resume.git import github as gh
from resume.ws import Workspace


_workspace: Workspace | None = None


def _is_workspace_path(path: Path) -> bool:
    return any(child.name == "resume.toml" for child in path.iterdir())


def _find_workspace() -> Path | None:
    path = Path(os.getcwd())
    if _is_workspace_path(path):
        return path

    return next((parent for parent in path.parents if _is_workspace_path(parent)), None)


def callback(
    workspace: Annotated[
        Path | None,
        typer.Option(help="Path to the workspace directory."),
    ] = _find_workspace(),
) -> None:
    global _workspace
    if workspace is not None:
        _workspace = Workspace(workspace)
        if _workspace.environment.logfire:
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
    return gh.Client(workspace().environment.github_access_token)
