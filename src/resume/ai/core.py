from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings

from resume.settings import settings

base_model_settings = ModelSettings(
    extra_body={
        "require_parameters": True,
        "data_collection": "deny",
    }
)

openrouter = OpenRouterProvider(api_key=settings.openrouter_api_key.get_secret_value())

gemini_2_0_flash = OpenAIModel("google/gemini-2.0-flash-001", provider=openrouter)
gemini_2_5_flash = OpenAIModel(
    "google/gemini-2.5-flash-preview-05-20",
    provider=openrouter,
)
grok_3_mini = OpenAIModel("x-ai/grok-3-mini-beta", provider=openrouter)
