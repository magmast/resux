from contextlib import asynccontextmanager
from functools import cached_property
from typing import Literal, override

from pydantic import SecretStr
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings


base_model_settings = ModelSettings(
    temperature=0.5,
    extra_body={
        "require_parameters": True,
        "data_collection": "deny",
    },
)


class LazyModel(Model):
    _provider: OpenRouterProvider | None = None

    def __init__(
        self,
        name: Literal["x-ai/grok-3-mini-beta", "google/gemini-2.0-flash-001"] | str,
    ):
        self.name = name

    @classmethod
    def init(cls, openrouter_api_key: SecretStr):
        cls._provider = OpenRouterProvider(
            api_key=openrouter_api_key.get_secret_value()
        )

    @cached_property
    def wrapped(self):
        if not self._provider:
            raise ProviderUninitializedError()
        return OpenAIModel(self.name, provider=self._provider)

    @override
    async def request(self, *args, **kwargs):
        return await self.wrapped.request(*args, **kwargs)

    @asynccontextmanager
    @override
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ):
        async with self.wrapped.request_stream(
            messages,
            model_settings,
            model_request_parameters,
        ) as response_stream:
            yield response_stream

    @override
    def customize_request_parameters(
        self, model_request_parameters: ModelRequestParameters
    ) -> ModelRequestParameters:
        return self.wrapped.customize_request_parameters(model_request_parameters)

    @property
    @override
    def model_name(self) -> str:
        return self.wrapped.model_name

    @property
    @override
    def system(self) -> str:
        return self.wrapped.system


gemini_2_0_flash = LazyModel("google/gemini-2.0-flash-001")
grok_3_mini = LazyModel("x-ai/grok-3-mini-beta")


class ProviderUninitializedError(Exception):
    @override
    def __str__(self):
        return "Provider has not been initialized. Call resux.ai.init() first."
