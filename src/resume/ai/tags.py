from pydantic_ai import Agent

from resume import git
from resume.ai.core import base_model_settings, gemini_2_0_flash


agent = Agent(
    gemini_2_0_flash,
    model_settings=base_model_settings,
    output_type=list[str],
    instructions="""\
You are a specialized AI that analyzes software project summaries and returns a concise list of tags describing each project.

Your goal is to generate a high-quality set of descriptive tags that characterize the project, so that other AI agents can later use them to match relevant projects to job offers.

Output Format:
Return a list of lowercase tags as plain strings, without duplicates. Keep the list under 20 items. Do not include hashtags or formatting.

The tags should include:
- Technologies and languages used (e.g. `python`, `react`, `docker`, `graphql`)
- Project domain or purpose (e.g. `resume-builder`, `static-site-generator`, `ai-agent`, `monitoring`)
- Key features (e.g. `cli`, `rest-api`, `authentication`, `realtime`)
- Scale or scope indicators, if relevant (e.g. `multi-tenant`, `microservice`, `prototype`)

Do not include:
- Generic adjectives like `cool`, `simple`, `useful`
- Vague or abstract tags like `project`, `code`, `app` unless the summary itself is extremely minimal
- The project name as a tag

Only generate tags based on what is explicitly stated in the summary. Do not infer or speculate.""",
)


async def generate_tags(repo_tags: list[git.Tag], summary: str) -> list[str]:
    tags = ", ".join(tag.name for tag in repo_tags)
    result = await agent.run(f"""\
Repository tags: {tags}
Project summary:

{summary}""")
    return result.output
