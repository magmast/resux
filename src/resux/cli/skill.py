import typer

from resux import ai
from resux.cli._ctx import Context, contextual
from resux.util import asyncio_run


app = typer.Typer(name="skill", help="Tools for managing skills in your workspace.")


@app.command()
@asyncio_run
@contextual
async def guess(ctx: Context):
    """Guess the skill name based on your projects."""

    if not ctx.workspace.projects.get_size():
        raise RuntimeError(
            "Workspace does not have any project yet. Please create them first using `resux project summarize` command."
        )

    skills = await ai.guess_skills(ctx.workspace)
    for skill in skills:
        print(skill)
