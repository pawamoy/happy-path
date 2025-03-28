"""A simple profiler that records 'call' and 'return' events for a given function."""

import inspect
import re
import sys
from contextlib import contextmanager
from functools import partial
from gzip import GzipFile
from types import FrameType
from typing import IO, Any, Callable, Iterator, Literal, Pattern, Sequence, TextIO

import ujson

_builtins = set(dir(__builtins__))
_builtins.add("__builtins__")


def _safe_repr(obj: Any) -> str:
    try:
        return repr(obj)
    except Exception:  # noqa: BLE001
        return f"{obj.__class__.__module__}.{obj.__class__.__name__} object at {hex(id(obj))}"


def _sysprofile(
    frame: FrameType,
    event: Literal["call", "return", "c_call", "c_return", "c_exception"],
    arg: Any,
    *,
    include: Sequence[Pattern],
    exclude: Sequence[Pattern],
    record_globals: bool,
    stream_to: IO,
) -> None:
    if event in {"c_call", "c_return", "c_exception"}:
        return

    callee_frame = frame

    # Assert we can determine parent modules.
    if not (
        (caller_frame := frame.f_back)
        and (callee_module := inspect.getmodule(callee_frame))
        and (caller_module := inspect.getmodule(caller_frame))
    ):
        return

    # Compute caller and callee names.
    caller_name = f"{caller_module.__name__}.{caller_frame.f_code.co_qualname}"  # type: ignore[attr-defined,unused-ignore]
    callee_name = f"{callee_module.__name__}.{callee_frame.f_code.co_qualname}"  # type: ignore[attr-defined,unused-ignore]

    # Filter out events based on caller/callee names and inclusion/exclusion patterns.
    if not (any(ip.match(caller_name) for ip in include) and any(ip.match(callee_name) for ip in include)):
        return
    if any(ep.match(caller_name) for ep in exclude) or any(ep.match(callee_name) for ep in exclude):
        return

    # Prepare event data.
    event_data: dict[str, Any] = {
        "event": event,
        "caller": {
            "name": caller_name,
            "source": {"path": inspect.getfile(caller_module), "lineno": caller_frame.f_lineno},
            "locals": caller_frame.f_locals,
        },
        "callee": {
            "name": callee_name,
            "source": {"path": inspect.getfile(callee_module), "lineno": callee_frame.f_lineno},
            "locals": callee_frame.f_locals,
        },
    }

    # Add caller and callee globals.
    if record_globals:
        event_data["caller"]["globals"] = {k: v for k, v in caller_frame.f_globals.items() if k not in _builtins}
        event_data["callee"]["globals"] = {k: v for k, v in callee_frame.f_globals.items() if k not in _builtins}

    # Add return value for 'return' events.
    if event == "return":
        event_data["return_value"] = arg

    # Serialize event and send to given stream.
    ujson.dump(event_data, stream_to, default=_safe_repr, escape_forward_slashes=False)
    print(file=stream_to)


class _GzipWriter(GzipFile):
    def write(self, data: str) -> int:  # type: ignore[override]
        return super().write(data.encode())


@contextmanager
def _output(to: str | IO, compression: int) -> Iterator[IO]:
    if not isinstance(to, str):
        yield to
        return
    if compression:
        with _GzipWriter(to + ".gz", "w", compresslevel=compression) as stream:
            yield stream  # type: ignore[misc]
    else:
        with open(to, "w") as stream:
            yield stream


def record(
    function: Callable,
    args: tuple | None = None,
    kwargs: dict | None = None,
    *,
    include: Sequence[str | Pattern] | None = None,
    exclude: Sequence[str | Pattern] | None = None,
    record_globals: bool = True,
    stream_to: str | TextIO | None = None,
    compression: int = 0,
) -> None:
    """Run a function with profiling enabled, recording 'call' and 'return' events.

    Parameters:
        function: The function to profile.
        args: Optional arguments to pass to the function.
        kwargs: Optional keyword arguments to pass to the function.
        include: A list of regular expression used to filter out events.
            Only events for which the caller/callee's name matches
            at least one of the inclusion patterns will be recorded.
            By default, it will use a regular expression matching names
            contained within the given function's package. For example,
            if the function comes from a package called `hello`, then the pattern
            will match names like `hello`, `hello.world`, `hello.other.worlds`, etc.
        exclude: A list of regular expression used to filter out events.
            Events for which the caller/callee name matches at least one of the
            exclusion patterns will not be recorded. By default, no events are excluded.
        record_globals: Whether to include globals for each event.
        stream_to: The IO handler to write JSON serialized events to.
    """
    # Set default arguments.
    if not include and not exclude:
        origin_function = function.func if isinstance(function, partial) else function
        try:
            module = inspect.getmodule(origin_function).__name__  # type: ignore[union-attr]
        except AttributeError as error:
            raise ValueError(
                "Can't determine regular expression to filter events based on caller/callee's name",
            ) from error
        # By default, keep events within function's package.
        module = module.split(".", 1)[0]
        include = [re.compile(rf"{module}(?:\..+)?")]
    else:
        # Cast patterns to compiled regular expressions.
        if include:
            include = [re.compile(ip) if isinstance(ip, str) else ip for ip in include]
        if exclude:
            exclude = [re.compile(ep) if isinstance(ep, str) else ep for ep in exclude]

    args = args or ()
    kwargs = kwargs or {}
    stream_to = stream_to or sys.stdout

    # Enable profiling and run function.
    with _output(stream_to, compression) as stream:
        profiler = partial(
            _sysprofile,
            include=include,
            exclude=exclude,
            record_globals=record_globals,
            stream_to=stream,
        )
        sys.setprofile(profiler)
        function(*args, **kwargs)
        sys.setprofile(None)
