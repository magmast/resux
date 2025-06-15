import asyncio
from typing import Annotated, cast
from urllib.parse import urlparse

import questionary
import typer

from resux.cli._ctx import Context, contextual
from resux.util import asyncio_run
from resux.ws import Profile


class _UnsupportedError(Exception):
    pass


def _scrap_github(url: str) -> Profile:
    parsed = urlparse(url)
    if parsed.hostname != "github.com":
        raise _UnsupportedError()

    username = parsed.path.rstrip("/").split("/")[-1]

    return Profile(
        id="github",
        network="GitHub",
        username=username,
        website=url,
        icon="github",
    )


def _scrap_gitlab(url: str) -> Profile:
    parsed = urlparse(url)
    if parsed.hostname != "gitlab.com":
        raise _UnsupportedError()

    username = parsed.path.rstrip("/").split("/")[-1]

    return Profile(
        id="gitlab",
        network="GitLab",
        username=username,
        website=url,
        icon="gitlab",
    )


def _scrap_linkedin(url: str) -> Profile:
    parsed = urlparse(url)
    if parsed.hostname != "www.linkedin.com":
        raise _UnsupportedError()

    username = parsed.path.rstrip("/").split("/")[-1]

    return Profile(
        id="linkedin",
        network="LinkedIn",
        username=username,
        website=url,
        icon="linkedin",
    )


_SCRAPPERS = (_scrap_github, _scrap_gitlab, _scrap_linkedin)


def _scrap(url: str) -> Profile:
    for scrapper in _SCRAPPERS:
        try:
            return scrapper(url)
        except _UnsupportedError:
            continue

    raise _UnsupportedError("Unsupported URL")


app = typer.Typer(name="profile", help="Manage resume profiles.")


@app.command(name="list")
@asyncio_run
@contextual
async def list_(ctx: Context) -> None:
    """List all profiles."""

    async for profile in ctx.workspace.profiles:
        print(f"[{profile.id}] {profile.network}: {profile.username}")


@app.command()
@asyncio_run
@contextual
async def add(ctx: Context, url: str) -> None:
    """Add a profile to the resume directory."""

    profile = _scrap(url)
    if await ctx.workspace.profiles.contains(profile.id):
        if not await questionary.confirm(
            "Profile already exists. Overwrite?"
        ).ask_async():
            return

    await ctx.workspace.profiles.set(profile)


@app.command()
@asyncio_run
@contextual
async def delete(
    ctx: Context,
    ids: Annotated[list[str] | None, typer.Argument()] = None,
) -> None:
    """Delete a profile from the resume directory."""

    if ids is None:
        all_ids = ctx.workspace.profiles.get_ids()
        ids = cast(
            list[str],
            await questionary.checkbox(
                "Select profiles to delete", choices=all_ids
            ).ask_async(),
        )

    await asyncio.gather(*(ctx.workspace.profiles.delete(id) for id in ids))
