import asyncio
from functools import wraps
from typing import (
    Any,
    Callable,
    Coroutine,
    ParamSpec,
    TypeVar,
)


TParams = ParamSpec("TParams")
TReturn = TypeVar("TReturn")


def asyncio_run(
    func: Callable[TParams, Coroutine[Any, Any, TReturn]],
) -> Callable[TParams, TReturn]:
    @wraps(func)
    def wrapper(*args: TParams.args, **kwargs: TParams.kwargs) -> TReturn:
        return asyncio.run(func(*args, **kwargs))

    return wrapper
