from types import NoneType, UnionType
from typing import Any, TypeVar, get_args, get_origin

from pydantic import BaseModel, SecretStr
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
import questionary


class FormField:
    def __init__(self, message: str | None = None, *, skip: bool = False) -> None:
        self.message = message
        self.skip = skip


def _create_form_field(key: str, info: FieldInfo) -> questionary.FormField | None:
    if info.exclude:
        return

    field = next(
        (metadata for metadata in info.metadata if isinstance(metadata, FormField)),
        FormField(),
    )
    if field.skip:
        return

    origin = get_origin(info.annotation)
    if origin is UnionType:
        args = get_args(info.annotation)
        if len(args) != 2:
            raise ValueError(f'Unsupported union type "{info.annotation}"')

        not_none = tuple(
            arg for arg in get_args(info.annotation) if arg is not NoneType
        )
        if len(not_none) != 1:
            raise ValueError(f'Unsupported union type "{info.annotation}"')

        annotation = not_none[0]
    else:
        annotation = info.annotation

    if annotation is str:
        question = questionary.text(field.message or key)
    elif annotation is SecretStr:
        question = questionary.password(field.message or key)
    elif annotation is bool:
        question = questionary.confirm(
            field.message or key,
            default=True if info.default is PydanticUndefined else info.default,
        )
    elif annotation is None:
        return
    else:
        raise ValueError(f'Unsupported field type "{annotation}"')

    return questionary.FormField(key, question)


def create_from(model: type[BaseModel]) -> questionary.Form:
    return questionary.Form(
        *filter(
            None,
            (
                _create_form_field(key, field)
                for key, field in model.model_fields.items()
            ),
        )
    )


T = TypeVar("T", bound=BaseModel)


async def ask_async(model: type[T], extra_kwargs: dict[str, Any] = {}) -> T:
    form = create_from(model)
    data = await form.ask_async()
    return model(**data, **extra_kwargs)
