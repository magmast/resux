import asyncio
from typing import Annotated, cast
from urllib.parse import urlparse

import questionary
import typer

from resux import ws
from resux.cli import _state
from resux.utils import asyncio_run


class _UnsupportedError(Exception):
    pass


def _scrap_github(url: str) -> ws.Profile:
    parsed = urlparse(url)
    if parsed.hostname != "github.com":
        raise _UnsupportedError()

    username = parsed.path.rstrip("/").split("/")[-1]

    return ws.Profile(
        id="github",
        network="GitHub",
        username=username,
        website=url,
        icon="github",
    )


def _scrap_gitlab(url: str) -> ws.Profile:
    parsed = urlparse(url)
    if parsed.hostname != "gitlab.com":
        raise _UnsupportedError()

    username = parsed.path.rstrip("/").split("/")[-1]

    return ws.Profile(
        id="gitlab",
        network="GitLab",
        username=username,
        website=url,
        icon="gitlab",
    )


def _scrap_linkedin(url: str) -> ws.Profile:
    parsed = urlparse(url)
    if parsed.hostname != "www.linkedin.com":
        raise _UnsupportedError()

    username = parsed.path.rstrip("/").split("/")[-1]

    return ws.Profile(
        id="linkedin",
        network="LinkedIn",
        username=username,
        website=url,
        icon="linkedin",
    )


_SCRAPPERS = (_scrap_github, _scrap_gitlab, _scrap_linkedin)


def _scrap(url: str) -> ws.Profile:
    for scrapper in _SCRAPPERS:
        try:
            return scrapper(url)
        except _UnsupportedError:
            continue

    raise _UnsupportedError("Unsupported URL")


app = typer.Typer(name="profile", help="Manage resume profiles.")


@app.command(name="list")
@asyncio_run
async def list_() -> None:
    """List all profiles."""

    workspace = _state.workspace()
    async for profile in workspace.profiles:
        print(f"[{profile.id}] {profile.network}: {profile.username}")


@app.command()
@asyncio_run
async def add(url: str) -> None:
    """Add a profile to the resume directory."""

    profile = _scrap(url)
    workspace = _state.workspace()
    if await workspace.profiles.contains(profile.id):
        if not await questionary.confirm(
            "Profile already exists. Overwrite?"
        ).ask_async():
            return

    await workspace.profiles.set(profile)


@app.command()
@asyncio_run
async def delete(ids: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    """Delete a profile from the resume directory."""

    workspace = _state.workspace()
    if ids is None:
        all_ids = await workspace.profiles.ids()
        ids = cast(
            list[str],
            await questionary.checkbox(
                "Select profiles to delete", choices=all_ids
            ).ask_async(),
        )

    await asyncio.gather(*(workspace.profiles.delete(id) for id in ids))
