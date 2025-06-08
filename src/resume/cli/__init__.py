from pathlib import Path
from typing import Annotated

import typer


from resume import form
from resume import ws
from resume.cli import _state
from resume.utils import asyncio_run


app = typer.Typer(callback=_state.callback)


@app.command()
@asyncio_run
async def init(
    path: Annotated[Path, typer.Argument(help="Path to the new workspace directory.")],
    override: Annotated[
        bool,
        typer.Option(help="Override the directory/file if it already exists."),
    ] = False,
) -> None:
    """Initialize a resume repository."""

    env = await form.ask_async(ws.Environment)
    user = await form.ask_async(ws.User)
    await ws.Workspace.init(path, override=override, environment=env, user=user)


@app.command()
def create() -> None:
    """Create a resume tailored for a job posting."""

    raise NotImplementedError


def main() -> None:
    app()
