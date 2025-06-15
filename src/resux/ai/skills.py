import asyncio
from dataclasses import dataclass
from typing import Literal

from pydantic_ai import Agent

from resux.ai._util import base_model_settings, gemini_2_0_flash
from resux.ws import Workspace
from resux.ws.resource import Project


@dataclass
class Skill:
    name: str
    level: Literal["beginner", "intermediate", "proficient", "advanced", "expert"]
    description: str


skills_agent = Agent(
    gemini_2_0_flash,
    model_settings=base_model_settings,
    output_type=list[Skill],
    instructions="Based on the user's project determine his skills for a resume.",
)


async def guess_project_skills(project: Project):
    result = await skills_agent.run(project.model_dump_json())
    return result.output


merge_agent = Agent(
    gemini_2_0_flash,
    model_settings=base_model_settings,
    output_type=list[Skill],
    instructions="From a list of user's skills generated for each of his projects, create a coherent list of skills for a resume.",
)


async def guess_skills(workspace: Workspace):
    async def handle_project(project: Project):
        skills = await guess_project_skills(project)
        skills_md = "\n".join(
            f"- {skill.name} ({skill.level}): {skill.description}" for skill in skills
        )
        return f"*{project.id}*:\n\n{skills_md}"

    projects = [project async for project in workspace.projects]
    skill_mds = await asyncio.gather(*(handle_project(project) for project in projects))
    result = await merge_agent.run("\n\n".join(skill_mds))
    return result.output
