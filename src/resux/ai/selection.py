from dataclasses import dataclass
from pydantic_ai import Agent

from resux import ws
from resux.ai.core import gemini_2_0_flash, base_model_settings
from resux.job_boards import Posting


@dataclass
class SelectedProject:
    reasoning: str
    id: str


agent = Agent(
    model=gemini_2_0_flash,
    output_type=list[SelectedProject],
    model_settings=base_model_settings,
    instructions="""\
You're a technical resume screener.

Given a list of user projects and a job posting, select up to 6 projects that
best match the posting.""",
)


async def select_projects(
    workspace: ws.Workspace,
    posting: Posting,
) -> list[SelectedProject]:
    projects_desc = "\n\n---\n\n".join(
        [
            f"## {project.id}\n\n{project.summary}"
            async for project in workspace.projects
        ]
    )

    reqs = "\n".join(
        f"- {req['name']} ({req['level']})"
        for req in posting["skills"]
        if not req["optional"]
    )

    nice_to_have = "\n".join(
        f"- {req['name']} ({req['level']})"
        for req in posting["skills"]
        if req["optional"]
    )

    result = await agent.run(
        f"""\
Projects:

{projects_desc}

Posting:

# {posting["title"]}

{posting["description"]}

## Requirements

{reqs}

## Nice to Have

{nice_to_have}"""
    )

    return result.output
