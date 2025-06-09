from contextlib import asynccontextmanager
from contextvars import ContextVar
from functools import cached_property
from typing import AsyncIterator, override
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models import Model, ModelRequestParameters, StreamedResponse
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings


base_model_settings = ModelSettings(
    extra_body={
        "require_parameters": True,
        "data_collection": "deny",
    }
)


class LazyOpenRouterModel(Model):
    _provider: ContextVar[OpenRouterProvider] = ContextVar("_provider")

    def __init__(self, name: str) -> None:
        self.name = name

    @classmethod
    def set_provider(cls, provider: OpenRouterProvider) -> None:
        cls._provider.set(provider)

    @cached_property
    def wrapped(self) -> Model:
        provider = self._provider.get()
        return OpenAIModel(self.name, provider=provider)

    @override
    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        return await self.wrapped.request(
            messages,
            model_settings,
            model_request_parameters,
        )

    @override
    @asynccontextmanager
    async def request_stream(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> AsyncIterator[StreamedResponse]:
        async with self.wrapped.request_stream(
            messages,
            model_settings,
            model_request_parameters,
        ) as response_stream:
            yield response_stream

    @override
    def customize_request_parameters(
        self,
        model_request_parameters: ModelRequestParameters,
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

    @property
    @override
    def base_url(self) -> str | None:
        return self.wrapped.base_url


gemini_2_0_flash = LazyOpenRouterModel("google/gemini-2.0-flash-001")
gemini_2_5_flash = LazyOpenRouterModel("google/gemini-2.5-flash-preview-05-20")
grok_3_mini = LazyOpenRouterModel("x-ai/grok-3-mini-beta")
