from dataclasses import dataclass
from pydantic_ai import Agent, ModelRetry, RunContext

from resux.ai.core import base_model_settings, grok_3_mini
from resux.git import File, Repo


@dataclass
class Deps:
    files: list[File]


agent = Agent(
    grok_3_mini,
    deps_type=Deps,
    output_type=str,
    model_settings=base_model_settings,
    instructions="""\
You're a senior software developer.

Your task is to analyze and summarize the repository provided by the user.

Your summary must include:
- A concise, human-readable title
- A high-level overview of what the project does and what problem it solves
- Key features and capabilities, especially anything unique or technically interesting
- Noteworthy design decisions or architectural patterns, if identifiable
- Key technologies, frameworks, or libraries used

Instructions:
- Use the `read_file` tool to gather the necessary information — especially README files, main source files, and config files. Don't stop at surface-level descriptions; dive into the code to understand how things work.
- Do not speculate. If you're unsure, read more files. Avoid vague or cautious language like "likely", "appears to", or "might".
- Do not include disclaimers or meta-comments in your response. Your output must be the final summary, nothing else.
- Avoid reading irrelevant files like lockfiles (`go.sum`, `package-lock.json`, `uv.lock`, etc.).
- You do not need to ask the user before using tools.""",
)


@agent.tool
async def read_file(ctx: RunContext[Deps], filepath: str) -> str:
    """Get the content of a file in the repository."""

    for file in ctx.deps.files:
        if file.path == filepath:
            return file.content.decode()

    raise ModelRetry(
        "Specified file does not exist or is a directory. "
        "Are you sure that the path you're trying to read is exists and is a file?"
    )


async def summarize_project(repo: Repo) -> str:
    """Summarize a project."""

    files = [file async for file in repo.get_files()]
    structure = "\n".join([f"- {file.path}" for file in files])
    result = await agent.run(
        f"Project structure:\n\n{structure}",
        deps=Deps(files=files),
    )

    return result.output
