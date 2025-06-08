from functools import cached_property
from types import NoneType, UnionType
from typing import Any, Generic, Iterator, TypeVar, get_args, get_origin

from pydantic import BaseModel, SecretStr
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
import questionary


class FormField:
    def __init__(self, message: str | None = None, *, skip: bool = False) -> None:
        self.message = message
        self.skip = skip


class _Field:
    def __init__(self, key: str, info: FieldInfo) -> None:
        self.key = key
        self.info = info
        self.default = info.get_default()

    @cached_property
    def annotation(self) -> type:
        origin = get_origin(self.info.annotation)
        if origin is not UnionType:
            if self.info.annotation is not None:
                return self.info.annotation
            raise TypeError

        args = get_args(self.info.annotation)
        if len(args) != 2:
            raise TypeError

        not_none = tuple(arg for arg in args if arg is not NoneType)
        if len(not_none) != 1:
            raise TypeError

        return not_none[0]

    @cached_property
    def metadata(self) -> FormField:
        form_fields = tuple(
            metadata
            for metadata in self.info.metadata
            if isinstance(metadata, FormField)
        )
        if len(form_fields) > 1:
            raise ValueError

        return form_fields[0] if form_fields else FormField()

    @property
    def title(self) -> str:
        return self.info.title or self.key

    @property
    def message(self) -> str:
        return self.metadata.message or self.title

    @cached_property
    def default(self) -> Any:
        return self.info.get_default()

    @property
    def empty(self) -> Any:
        if self.annotation is str or self.annotation is SecretStr:
            return ""
        elif self.annotation is bool:
            return True
        else:
            raise TypeError

    @property
    def default_or_empty(self) -> Any:
        return (
            self.default
            if issubclass(self.default.__class__, self.annotation)
            else self.empty
        )

    def empty_to_default(self, value: Any) -> Any:
        if value != self.empty:
            return value
        if self.default is PydanticUndefined:
            raise ValueError
        return self.default

    def validate(self, value: Any) -> bool | str:
        if self.default is PydanticUndefined and value == self.empty:
            return f"{self.title} is required"
        return True

    @cached_property
    def question(self) -> questionary.Question | None:
        if self.info.exclude or self.metadata.skip:
            return None

        if self.annotation is str:
            return questionary.text(
                self.message,
                default=self.default_or_empty,
                validate=self.validate,
            )
        elif self.annotation is SecretStr:
            return questionary.password(
                self.message,
                default=self.default_or_empty,
                validate=self.validate,
            )
        elif self.annotation is bool:
            return questionary.confirm(self.message, default=self.default_or_empty)
        else:
            raise TypeError


T = TypeVar("T", bound=BaseModel)


class Form(Generic[T]):
    def __init__(self, model_type: type[T]) -> None:
        self.model_type = model_type
        self._fields: dict[str, _Field] = {}
        self._form = questionary.Form(*self._build_fields())

    async def ask(self, *, defaults: dict[str, Any] = {}) -> T:
        raw = await self._form.ask_async()
        data = {
            key: self._fields[key].empty_to_default(value) for key, value in raw.items()
        }
        return self.model_type(**defaults, **data)

    def _build_fields(self) -> Iterator[questionary.FormField]:
        def build_field(key: str, info: FieldInfo) -> questionary.FormField | None:
            try:
                return self._build_field(key, info)
            except Exception as e:
                e.add_note(f"Failed to create form field for {key}")
                raise

        return filter(
            None,
            (
                build_field(key, info)
                for key, info in self.model_type.model_fields.items()
            ),
        )

    def _build_field(self, key: str, info: FieldInfo) -> questionary.FormField | None:
        try:
            self._fields[key] = _Field(key, info)
            question = self._fields[key].question
            return questionary.FormField(key, question) if question else None
        except Exception as e:
            e.add_note(f"Failed to create form field for {key}")
            raise


async def ask(model: type[T], *, defaults: dict[str, Any] = {}) -> T:
    form = Form(model)
    return await form.ask(defaults=defaults)
