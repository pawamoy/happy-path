"""Module that contains the command line application."""

# Why does this file exist, and why not put this in `__main__`?
#
# You might be tempted to import things from `__main__` later,
# but that will cause problems: the code will get executed twice:
#
# - When you run `python -m happy_path` python will execute
#   `__main__.py` as a script. That means there won't be any
#   `happy_path.__main__` in `sys.modules`.
# - When you import `__main__` it will get executed again (as a module) because
#   there's no `happy_path.__main__` in `sys.modules`.

import runpy
from dataclasses import asdict, dataclass
from functools import partial, wraps
from inspect import cleandoc
from pathlib import Path
from typing import Any, Callable

import cappa
from typing_extensions import Annotated as An
from typing_extensions import Doc

from happy_path import debug
from happy_path.recorder import record
from happy_path.renderer import render

NAME = "happy-path"


def print_and_exit(
    func: An[Callable[[], str | None], Doc("A function that returns or prints a string.")],
    code: An[int, Doc("The status code to exit with.")] = 0,
) -> Callable[[], None]:
    """Argument action callable to print something and exit immediately."""

    @wraps(func)
    def _inner() -> None:
        raise cappa.Exit(func() or "", code=code)

    return _inner


@dataclass(kw_only=True)
class HelpOption:
    """Reusable class to share a `-h`, `--help` option."""

    help: An[
        bool,
        cappa.Arg(
            short="-h",
            long=True,
            action=cappa.ArgAction.help,
        ),
        Doc("Print the program help and exit."),
    ] = False

    @property
    def _options(self) -> dict[str, Any]:
        options = asdict(self)
        options.pop("help", None)
        return options


@cappa.command(
    name="record",
    help="Record the execution of a Python program.",
    description=cleandoc(
        """
        Run a Python program and record its execution in a JSONL file.
        The execution is recorded as a list of `call` and `return` events.
        """,
    ),
)
@dataclass(kw_only=True)
class CommandRecord(HelpOption):
    """Command to record the execution of a Python program."""

    script: An[
        str,
        cappa.Arg(),
        Doc("""Python code to execute, or path to a Python script to execute."""),
    ]
    prepare: An[
        str | None,
        cappa.Arg(short="-p", long=True),
        Doc(
            """Python code to execute before the script/code.
            This is useful if you want to avoid recording events occurring at import time:
            `-p 'import pkg1, pkg2'`.
            """,
        ),
    ] = None
    include: An[
        list[str] | None,
        cappa.Arg(short="-i", long=True),
        Doc("""Inclusion filters to use when recording."""),
    ] = None
    include_packages: An[
        list[str] | None,
        cappa.Arg(short="-I", long=True),
        Doc("""Record events occurring within these packages. Shortcut for `-i 'package(?:\\..+)?'`."""),
    ] = None
    exclude: An[
        list[str] | None,
        cappa.Arg(short="-e", long=True),
        Doc("""Exclusion filters to use when recording."""),
    ] = None
    exclude_packages: An[
        list[str] | None,
        cappa.Arg(short="-E", long=True),
        Doc("""Don't record events occurring within these packages. Shortcut for `-e 'package(?:\\..+)?'`."""),
    ] = None
    compression: An[
        int,
        cappa.Arg(short="-c", long=True),
        Doc("""Compression level (GZip) for the output, from 0 (no compression) to 9."""),
    ] = 1
    output: An[
        str,
        cappa.Arg(short="-o", long=True),
        Doc(
            """Path of the output file to write the events to.
            A `.gz` suffix is automatically appended when the output is compressed.
            """,
        ),
    ] = "events.jsonl"

    def __call__(self) -> int:  # noqa: D102
        exec_globals: dict[str, Any] = {"__name__": "__main__", "__file__": "<string>"}
        if self.prepare:
            exec(self.prepare, exec_globals)  # noqa: S102
        function: Callable[..., Any]
        if Path(self.script).exists():
            function = partial(runpy.run_path, self.script, init_globals=exec_globals, run_name="__main__")
        else:
            function = partial(exec, self.script, exec_globals)
        include = self.include or []
        exclude = self.exclude or []
        if self.include_packages:
            include.extend(f"{package}(?:\\..+)?" for package in self.include_packages)
        if self.exclude_packages:
            exclude.extend(f"{package}(?:\\..+)?" for package in self.exclude_packages)
        record(
            function,
            stream_to=self.output,
            compression=self.compression,
            include=include,
            exclude=exclude,
            record_globals=False,
        )
        return 0


@cappa.command(
    name="render",
    help="Render a flow graph from an events file.",
    description=cleandoc(
        """
        This command reads a JSONL file containing events and renders
        an SVG flow graph in an HTML file, with Javascript for interactivity.
        """,
    ),
)
@dataclass(kw_only=True)
class CommandRender(HelpOption):
    """Command to render a flow graph from an events file."""

    events_file: An[
        str,
        cappa.Arg(),
        Doc("""Path of the JSONL file containing events."""),
    ] = "events.jsonl"

    def __call__(self) -> Any:  # noqa: D102
        print(render(self.events_file))
        return 0


@cappa.command(
    name=NAME,
    help="Record and render Python program executions as SVG flow graphs.",
    description=cleandoc(
        """
        This tool lets you record the execution of a Python program and render
        an SVG flow graph from the recorded events. The flow graph is interactive
        and shows the call stack and the return values of each function.
        """,
    ),
)
@dataclass(kw_only=True)
class CommandMain(HelpOption):
    """Command to record and render Python program executions as SVG flow graphs."""

    subcommand: An[cappa.Subcommands[CommandRecord | CommandRender], Doc("The selected subcommand.")]

    version: An[
        bool,
        cappa.Arg(
            short="-V",
            long=True,
            action=print_and_exit(debug.get_version),
            num_args=0,
            help="Print the program version and exit.",
        ),
    ] = False

    debug_info: An[
        bool,
        cappa.Arg(long=True, action=print_and_exit(debug.print_debug_info), num_args=0),
        Doc("Print debug information."),
    ] = False

    completion: An[
        bool,
        cappa.Arg(
            long=True,
            action=cappa.ArgAction.completion,
            choices=("complete", "generate"),
            help="Print shell-specific completion source.",
        ),
    ] = False


def main(
    args: An[list[str] | None, Doc("Arguments passed from the command line.")] = None,
) -> An[int, Doc("An exit code.")]:
    """Run the main program.

    This function is executed when you type `happy-path` or `python -m happy_path`.
    """
    output = cappa.Output(error_format=f"[bold]{NAME}[/]: [bold red]error[/]: {{message}}")
    return cappa.invoke(CommandMain, argv=args, output=output, backend=cappa.backend, completion=False, help=False)
