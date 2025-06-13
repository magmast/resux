from pydantic import SecretStr
from resux.ai._util import LazyModel
from resux.ai.activity import find_last_major_activity
from resux.ai.selection import select_projects
from resux.ai.summary import summarize_project
from resux.ai.tags import generate_tags


def init(openrouter_api_key: SecretStr):
    LazyModel.init(openrouter_api_key)


__all__ = [
    "find_last_major_activity",
    "generate_tags",
    "init",
    "select_projects",
    "summarize_project",
]
