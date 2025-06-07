import asyncio
from enum import StrEnum
from pathlib import Path
from pprint import pprint
from typing import Annotated

import logfire
import questionary
from typer import Argument, Option, Typer

from resume import ai
from resume.git import Repo, github
from resume.job_boards.no_fluff_jobs import Client as NfjClient
from resume.settings import settings
from resume.utils import Project, Workspace, asyncio_run

logfire.configure()
logfire.instrument_pydantic_ai()


project_app = Typer(
    name="project",
    help="Tools for managing project summaries in your workspace.",
)
gh_client = github.Client(settings.github_access_token)
workspace: Workspace = None  # type: ignore


_confirm_lock = asyncio.Lock()


class ConflictStrategy(StrEnum):
    OVERWRITE = "overwrite"
    SKIP = "skip"
    ASK = "ask"

    async def can_write(self, workspace: Workspace, id: str) -> bool:
        if self == ConflictStrategy.OVERWRITE:
            return True

        already_exists = await workspace.projects.acontains(id)
        if not already_exists:
            return True

        if self == ConflictStrategy.SKIP:
            return False

        async with _confirm_lock:
            return await questionary.confirm(
                f"Project {id} already exists. Overwrite?"
            ).ask_async()


@project_app.command()
@asyncio_run
async def summarize(
    names: Annotated[
        list[str] | None,
        Argument(
            help=(
                "GitHub repositories to summarize. "
                "Use just the name for repositories owned by the authenticated user (e.g. 'my-repo'), "
                "or the full name for others (e.g. 'user/repo'). "
                "If not provided, an interactive project picker will be shown."
            ),
        ),
    ] = None,
    conflict_strategy: Annotated[
        ConflictStrategy,
        Option(
            help=(
                "What to do if a summary already exists: "
                "'overwrite' to replace it, 'skip' to leave it unchanged, "
                "or 'ask' (default) to prompt before replacing."
            ),
        ),
    ] = ConflictStrategy.ASK,
) -> None:
    """Generate a summary for one or more GitHub projects."""

    async def summarize_repo(repo: Repo) -> None:
        if not await conflict_strategy.can_write(workspace, repo.full_name):
            return

        async with asyncio.TaskGroup() as tg:
            summary_task = tg.create_task(ai.summarize_project(repo))
            last_major_activity_task = tg.create_task(ai.find_last_major_activity(repo))
        summary = await summary_task
        last_major_activity = await last_major_activity_task
        await workspace.projects.write(
            Project(
                id=repo.full_name,
                summary=summary,
                tags=await ai.generate_tags(summary),
                last_major_activity=last_major_activity["date"],
            )
        )

    user = await gh_client.user
    if names:
        full_names = [name if "/" in name else f"{user.login}/{name}" for name in names]
        repos = await asyncio.gather(*(map(gh_client.repos.__getitem__, full_names)))
    else:
        all_repos = user.repos
        repos: list[Repo] = await questionary.checkbox(
            "Select repositories to summarize:",
            choices=[
                questionary.Choice(title=repo.full_name, value=repo)
                async for repo in all_repos
            ],
        ).ask_async()

    async with asyncio.TaskGroup() as tg:
        for repo in repos:
            tg.create_task(summarize_repo(repo))


@project_app.command()
@asyncio_run
async def delete(
    ids: Annotated[
        list[str] | None, Argument(help="ID of the project to delete.")
    ] = None,
) -> None:
    """Delete projects from the workspace."""

    if ids is None:
        selected_ids: list[str] = await questionary.checkbox(
            "Select projects to delete:",
            choices=[id async for id in workspace.projects.ids],
        ).ask_async()
        ids = selected_ids

    async with asyncio.TaskGroup() as tg:
        for id in ids:
            tg.create_task(workspace.projects.adel(id))


app = Typer()
app.add_typer(project_app)


@app.callback()
def callback(
    workspace_path: Annotated[
        Path,
        Option(
            "--workspace",
            help="Path to the workspace directory.",
        ),
    ] = settings.workspace,
) -> None:
    global workspace
    workspace = Workspace(workspace_path)


@app.command()
@asyncio_run
async def create(
    url: Annotated[str, Argument(help="URL to the job posting.")],
) -> None:
    """Create resume tailored for a job posting."""

    async with NfjClient() as client:
        posting = await client.get_posting(url)
        selected_projects = await ai.select_projects(workspace, posting)
        pprint(selected_projects)


# TODO: Remove this command
@app.command()
@asyncio_run
async def patch_projects() -> None:
    async def append_last_major_activity(project: Project) -> None:
        project.tags = await ai.generate_tags(project.summary)
        await workspace.projects.write(project)

    async with asyncio.TaskGroup() as tg:
        async for project in workspace.projects:
            tg.create_task(append_last_major_activity(project))


def main() -> None:
    app()
