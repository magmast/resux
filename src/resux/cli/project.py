import asyncio
from enum import StrEnum
from typing import Annotated

import questionary
import typer

from resux import ai
from resux.cli._ctx import Context, contextual
from resux.git import Repo
from resux.util import asyncio_run
from resux.ws.resource import Project


_conflict_lock = asyncio.Lock()


class ConflictStrategy(StrEnum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    ASK = "ask"

    async def _can_write(self, ctx: Context, id: str) -> bool:
        if self == ConflictStrategy.OVERWRITE:
            return True

        exists = await ctx.workspace.projects.contains(id)
        if not exists:
            return True

        if self == ConflictStrategy.SKIP:
            return False

        async with _conflict_lock:
            return await questionary.confirm(
                f'Project "{id}" already exists. Overwrite?',
                default=False,
            ).ask_async()


app = typer.Typer(name="project", help="Tools for managing projects in your workspace.")


@app.command()
@asyncio_run
@contextual
async def summarize(
    ctx: Context,
    names: Annotated[
        list[str] | None,
        typer.Argument(help="Names of GitHub repositories to summarize."),
    ] = None,
    conflict_strategy: Annotated[
        ConflictStrategy,
        typer.Option(
            help=(
                "What to do if a summary already exists: "
                "'overwrite' to replace it, 'skip' to leave it unchanged, "
                "or 'ask' (default) to prompt before replacing."
            )
        ),
    ] = ConflictStrategy.ASK,
) -> None:
    """Generate a summary for one or more GitHub projects."""

    async def summarize_repo(repo: Repo) -> None:
        if not await conflict_strategy._can_write(ctx, repo.full_name):
            return

        summary, last_major_activity, tags, languages = await asyncio.gather(
            ai.summarize_project(repo),
            ai.find_last_major_activity(repo),
            repo.tags.all(),
            repo.get_languages(),
        )

        await ctx.workspace.projects.set(
            Project(
                id=repo.full_name,
                summary=summary,
                tags=await ai.generate_tags(tags, summary),
                last_major_activity=last_major_activity.date,
                stars=repo.stars,
                languages=languages,
            )
        )

    user = await ctx.github.get_user()
    if names:
        full_names = [name if "/" in name else f"{user.login}/{name}" for name in names]
        repos = await asyncio.gather(
            *(ctx.github.repos.get(name) for name in full_names)
        )
    else:
        all_repos = user.repos
        repos: list[Repo] = await questionary.checkbox(
            "Select repositories to summarize",
            choices=[
                questionary.Choice(title=repo.full_name, value=repo)
                async for repo in all_repos
            ],
        ).ask_async()

    await asyncio.gather(*(summarize_repo(repo) for repo in repos))


@app.command()
@asyncio_run
@contextual
async def delete(
    ctx: Context,
    ids: Annotated[
        list[str] | None,
        typer.Argument(help="ID of the project to delete."),
    ] = None,
) -> None:
    """Delete projects from the workspace."""

    if ids is None:
        all_ids = ctx.workspace.projects.get_ids()
        if not all_ids:
            raise RuntimeError("No projects found in the workspace")

        selected_ids: list[str] = await questionary.checkbox(
            "Select projects to delete",
            choices=all_ids,
        ).ask_async()
        ids = selected_ids

    await asyncio.gather(*(ctx.workspace.projects.delete(id) for id in ids))
