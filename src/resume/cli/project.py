import asyncio
from enum import StrEnum
from typing import Annotated

import questionary
import typer

from resume import ai, git, ws
from resume.cli import _state
from resume.utils import asyncio_run


_conflict_lock = asyncio.Lock()


class ConflictStrategy(StrEnum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    ASK = "ask"

    async def _can_write(self, id: str) -> bool:
        if self == ConflictStrategy.OVERWRITE:
            return True

        exists = await _state.workspace().projects.contains(id)
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
async def summarize(
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

    async def summarize_repo(repo: git.Repo) -> None:
        if not await conflict_strategy._can_write(repo.full_name):
            return

        summary, last_major_activity, tags = await asyncio.gather(
            ai.summarize_project(repo),
            ai.find_last_major_activity(repo),
            repo.tags[:],
        )

        await _state.workspace().projects.set(
            ws.Project(
                id=repo.full_name,
                summary=summary,
                tags=await ai.generate_tags(tags, summary),
                last_major_activity=last_major_activity.date,
                stars=repo.stars,
            )
        )

    user = await _state.github().user
    if names:
        full_names = [name if "/" in name else f"{user.login}/{name}" for name in names]
        repos = await asyncio.gather(
            *(map(_state.github().repos.__getitem__, full_names))
        )
    else:
        all_repos = user.repos
        repos: list[git.Repo] = await questionary.checkbox(
            "Select repositories to summarize",
            choices=[
                questionary.Choice(title=repo.full_name, value=repo)
                async for repo in all_repos
            ],
        ).ask_async()

    async with asyncio.TaskGroup() as tg:
        for repo in repos:
            tg.create_task(summarize_repo(repo))


@app.command()
@asyncio_run
async def delete(
    ids: Annotated[
        list[str] | None,
        typer.Argument(help="ID of the project to delete."),
    ] = None,
) -> None:
    """Delete projects from the workspace."""

    if ids is None:
        selected_ids: list[str] = await questionary.checkbox(
            "Select projects to delete",
            choices=[id async for id in _state.workspace().projects.ids],
        ).ask_async()
        ids = selected_ids

    async with asyncio.TaskGroup() as tg:
        for id in ids:
            tg.create_task(_state.workspace().projects.delete(id))
