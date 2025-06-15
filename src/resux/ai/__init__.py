from pydantic import SecretStr
from resux.ai._util import LazyModel
from resux.ai.activity import find_last_major_activity as find_last_major_activity
from resux.ai.selection import select_projects as select_projects
from resux.ai.skills import guess_skills as guess_skills
from resux.ai.summary import summarize_project as summarize_project
from resux.ai.tags import generate_tags as generate_tags


def init(openrouter_api_key: SecretStr):
    LazyModel.init(openrouter_api_key)
