from pathlib import Path
from typing import Annotated

import typer

from resux.cli import _ctx, profile, project, skill
from resux.util import asyncio_run, form
from resux.ws import Environment, User, Workspace


app = typer.Typer(callback=_ctx.callback)
app.add_typer(project.app)
app.add_typer(profile.app)
app.add_typer(skill.app)


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

    env = await form.ask(Environment)
    user = await form.ask(User)
    await Workspace.init(path, override=override, env=env, user=user)


@app.command()
def create() -> None:
    """Create a resume tailored for a job posting."""

    raise NotImplementedError


def main() -> None:
    app()
