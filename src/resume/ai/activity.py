from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict
from pydantic_ai import Agent, RunContext

from resume.ai.core import base_model_settings, gemini_2_0_flash
from resume.git import Repo


@dataclass
class Deps:
    repo: Repo


@dataclass
class Output:
    reasoning: str
    date: datetime


agent = Agent(
    model=gemini_2_0_flash,
    output_type=Output,
    deps_type=Deps,
    model_settings=base_model_settings,
    instructions="""\
You are a senior software engineer reviewing the latest activity in a Git repository.

Your task is to identify the most recent **major activity** based on commit messages and timestamps.

Major activities include:
- Adding a new feature
- Large or significant refactors
- Major changes to core functionality
- Introduction of new modules or major dependencies

Minor changes that should be ignored include:
- Small bug fixes
- README updates
- Documentation-only changes
- Simple build tweaks (like updating CI config or version bumps)

Use the `list_commits` tool to analyze recent commits. Examine them in chronological order, starting from the most recent, and stop once you find the latest activity that qualifies as major. Return the commit message and date for that major activity. If none are found in the recent range, indicate that explicitly.""",
)


class CommitDict(TypedDict):
    date: str
    message: str


@agent.tool
async def list_commits(
    ctx: RunContext[Deps],
    offset: int = 0,
    limit: int = 10,
) -> list[CommitDict]:
    """Get the list of commits in the specified range."""

    commits = await ctx.deps.repo.commits.slice(offset, offset + limit)
    return [
        CommitDict(date=commit.author_date.isoformat(), message=commit.message)
        for commit in commits
    ]


async def find_last_major_activity(repo: Repo) -> Output:
    result = await agent.run(deps=Deps(repo=repo))
    return result.output
