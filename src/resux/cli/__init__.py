from pathlib import Path
from typing import Annotated

import typer


from resux import form
from resux import ws
from resux.cli import _state, profile, project
from resux.utils import asyncio_run


app = typer.Typer(callback=_state.callback)
app.add_typer(project.app)
app.add_typer(profile.app)


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

    env = await form.ask(ws.Environment)
    user = await form.ask(ws.User)
    await ws.Workspace.init(path, override=override, environment=env, user=user)


@app.command()
def create() -> None:
    """Create a resume tailored for a job posting."""

    raise NotImplementedError


def main() -> None:
    app()
