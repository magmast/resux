from datetime import datetime
from typing import TypedDict
from pydantic_ai import Agent

from resume.ai.core import base_model_settings, gemini_2_0_flash
from resume.git import File, Repo, User


class Judgment(TypedDict):
    reasoning: str
    result: bool


agent = Agent(
    gemini_2_0_flash,
    model_settings=base_model_settings,
    output_type=Judgment,
    instructions="""\
Based on some basic information about a repository, determine whether it's
something worth mentioning on the user's resume.

To determine if the project is worth putting on a resume, consider:

- Does user made any significant contributions?
- Is the project small?
- And other things according to your experience""",
)


@agent.instructions
def add_todays_date() -> str:
    return f"\n\nToday's date: {datetime.now().isoformat()}"


async def judge_project(user: User, repo: Repo) -> Judgment:
    limit = 50
    count = 0
    files: list[File] = []
    async for file in repo.files:
        if count >= limit:
            break

        count += 1
        files.append(file)

    structure = "\n".join([f"- {file.path}" for file in files])
    if count == limit:
        structure += "\nNumber of files is limited to {limit}, but more files exist."

    prompt = f"""\
My name: {user.name}
My login: {user.login}
My email: {user.email}
Repository name: {repo.full_name}
Repository description: {repo.description}
Project structure:

{structure}

Latest commits:

{"\n".join([f"- {commit.author.name} ({commit.author.email}) on {commit.author_date.isoformat()}: {commit.message}" for commit in await repo.commits[:10]])}
"""

    readme = await repo.readme
    if readme:
        prompt += f"""

Readme:

```
{readme.content.decode()}
```"""

    result = await agent.run(prompt)
    return result.output
