"""CLI for running air-Q Cloud tool functions without an MCP client."""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, get_args, get_origin

import aiohttp
from mcp.server.fastmcp.utilities.types import Image

from mcp_airq_cloud.config import load_config
from mcp_airq_cloud.devices import DeviceManager
from mcp_airq_cloud.tools import read

ToolFunction = Any
TOOL_MODULES = (read,)
ERROR_PREFIXES = (
    "Configuration error:",
    "Authentication failed.",
    "Access denied for this device.",
    "Device not found in cloud.",
    "Cloud API error",
    "Network error:",
    "Request timed out.",
    "Chart rendering failed:",
    "Sensor(s) not available on this device:",
    "Specify at most one of",
    "last_hours must be positive.",
    "from_datetime must be before to_datetime.",
    "Multiple devices configured.",
)
SAFE_YAML_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _collect_tools() -> dict[str, ToolFunction]:
    """Collect tool functions in module definition order."""
    tools: dict[str, ToolFunction] = {}
    for module in TOOL_MODULES:
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            if inspect.iscoroutinefunction(value) and value.__module__ == module.__name__:
                tools[name] = value
    return tools


TOOLS = _collect_tools()


def _command_name(tool_name: str) -> str:
    """Convert a tool function name to a CLI command name."""
    return tool_name.replace("_", "-")


def _unwrap_optional(annotation: Any) -> Any:
    """Unwrap ``T | None`` to ``T``."""
    args = get_args(annotation)
    if type(None) in args:
        non_none = [arg for arg in args if arg is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return annotation


def _docstring(fn: ToolFunction) -> str:
    """Return a normalized docstring for a tool function."""
    return inspect.getdoc(fn) or "Run this command."


def _add_argument(parser: argparse.ArgumentParser, name: str, parameter: inspect.Parameter) -> None:
    """Add one CLI argument based on a tool function parameter."""
    annotation = parameter.annotation if parameter.annotation is not inspect._empty else str
    annotation = _unwrap_optional(annotation)
    option = f"--{name.replace('_', '-')}"
    kwargs: dict[str, Any] = {"dest": name}

    if annotation is bool:
        kwargs["action"] = argparse.BooleanOptionalAction
        if parameter.default is inspect._empty:
            kwargs["required"] = True
        else:
            kwargs["default"] = parameter.default
        parser.add_argument(option, **kwargs)
        return

    origin = get_origin(annotation)
    if origin is list:
        item_type = get_args(annotation)[0] if get_args(annotation) else str
        kwargs["nargs"] = "+"
        kwargs["type"] = item_type
    elif origin is Literal:
        choices = list(get_args(annotation))
        kwargs["choices"] = choices
        kwargs["type"] = type(choices[0]) if choices else str
    else:
        kwargs["type"] = annotation if isinstance(annotation, type) else str

    if parameter.default is inspect._empty:
        kwargs["required"] = True
    else:
        kwargs["default"] = parameter.default

    parser.add_argument(option, **kwargs)


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared output formatting flags."""
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--json",
        action="store_const",
        const="json",
        dest="output_mode",
        help="Serialize the command result as JSON.",
    )
    output_group.add_argument(
        "--yaml",
        action="store_const",
        const="yaml",
        dest="output_mode",
        help="Serialize the command result as YAML.",
    )
    parser.add_argument(
        "--compact-json",
        action="store_true",
        help="Serialize the command result as compact JSON.",
    )
    parser.set_defaults(output_mode="text", compact_json=False)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for all air-Q Cloud tool commands."""
    parser = argparse.ArgumentParser(
        prog="mcp-airq-cloud",
        description="Run air-Q Cloud commands directly from the terminal.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for tool_name, tool_fn in TOOLS.items():
        doc = _docstring(tool_fn)
        summary = doc.splitlines()[0]
        command = _command_name(tool_name)
        subparser = subparsers.add_parser(
            command,
            aliases=[tool_name],
            help=summary,
            description=doc,
        )
        subparser.set_defaults(tool_name=tool_name)
        _add_output_arguments(subparser)
        for name, parameter in inspect.signature(tool_fn).parameters.items():
            if name == "ctx":
                continue
            _add_argument(subparser, name, parameter)
        if tool_name == "plot_air_quality_history":
            subparser.add_argument(
                "--output",
                help="Write the plot to this file. Use '-' for stdout.",
            )

    return parser


def _build_context(manager: DeviceManager) -> Any:
    """Build the minimal context object expected by the tool functions."""
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=manager),
    )


async def _invoke_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Invoke one tool function inside a short-lived client session."""
    try:
        configs = load_config()
    except ValueError as exc:
        return f"Configuration error: {exc}"

    timeout = aiohttp.ClientTimeout(total=30, connect=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        manager = DeviceManager(session, configs)
        ctx = _build_context(manager)
        return await TOOLS[tool_name](ctx, **arguments)


async def _run_command(args: argparse.Namespace) -> Any:
    """Run the parsed CLI command."""
    tool_name = args.tool_name
    params = {name: getattr(args, name) for name in inspect.signature(TOOLS[tool_name]).parameters if name != "ctx"}
    return await _invoke_tool(tool_name, params)


def _write_image(image: Image, output_path: Path) -> None:
    """Write a rendered image to disk."""
    if image.data is not None:
        output_path.write_bytes(image.data)
        return
    if image.path is not None:
        output_path.write_bytes(image.path.read_bytes())
        return
    raise ValueError("No image payload available.")


def _write_stdout_bytes(data: bytes) -> None:
    """Write raw bytes to stdout for shell piping."""
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _write_stdout_text(text: str) -> None:
    """Write text to stdout without appending a newline."""
    sys.stdout.write(text)
    sys.stdout.flush()


def _default_output_path(args: argparse.Namespace) -> Path:
    """Choose a default output file for plot commands."""
    suffix = ".html" if args.output_format == "html" else ".png"
    return Path(f"{_command_name(args.tool_name)}{suffix}")


def _is_error_result(result: Any) -> bool:
    """Detect user-facing error strings returned by tool functions."""
    return isinstance(result, str) and result.startswith(ERROR_PREFIXES)


def _coerce_structured_data(result: Any) -> Any:
    """Parse JSON strings so they can be re-serialized for CLI output."""
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
    return result


def _yaml_key(value: str) -> str:
    """Render one YAML mapping key."""
    if SAFE_YAML_KEY.fullmatch(value):
        return value
    return json.dumps(value, ensure_ascii=False)


def _yaml_scalar(value: Any) -> str:
    """Render one YAML scalar."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _to_yaml(value: Any, indent: int = 0) -> str:
    """Serialize JSON-compatible data to a simple YAML representation."""
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines: list[str] = []
        for key, item in value.items():
            rendered_key = _yaml_key(str(key))
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}{rendered_key}:")
                lines.append(_to_yaml(item, indent + 2))
            elif isinstance(item, dict):
                lines.append(f"{prefix}{rendered_key}: {{}}")
            elif isinstance(item, list):
                lines.append(f"{prefix}{rendered_key}: []")
            else:
                lines.append(f"{prefix}{rendered_key}: {_yaml_scalar(item)}")
        return "\n".join(lines)

    if isinstance(value, list):
        if not value:
            return "[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}-")
                lines.append(_to_yaml(item, indent + 2))
            elif isinstance(item, dict):
                lines.append(f"{prefix}- {{}}")
            elif isinstance(item, list):
                lines.append(f"{prefix}- []")
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return "\n".join(lines)

    return f"{prefix}{_yaml_scalar(value)}"


def _should_stream_plot_to_stdout(args: argparse.Namespace) -> bool:
    """Decide whether plot output should be streamed to stdout."""
    return args.output == "-" or (args.output is None and not sys.stdout.isatty())


def _resolve_plot_output_path(args: argparse.Namespace) -> Path:
    """Resolve the target file path for plot output."""
    if args.output and args.output != "-":
        return Path(args.output)
    return _default_output_path(args)


def _emit_formatted_text(args: argparse.Namespace, result: Any) -> None:
    """Emit one non-binary result according to the selected output mode."""
    if args.output_mode == "text" and not args.compact_json:
        print(result)
        return

    data = _coerce_structured_data(result)
    if args.output_mode == "yaml":
        print(_to_yaml(data))
        return

    if args.output_mode == "json" or args.compact_json:
        if args.compact_json:
            print(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    print(result)


def _emit_result(args: argparse.Namespace, result: Any) -> None:
    """Emit the command result to stdout or a file."""
    if isinstance(result, Image):
        if _should_stream_plot_to_stdout(args):
            if result.data is not None:
                _write_stdout_bytes(result.data)
            elif result.path is not None:
                _write_stdout_bytes(result.path.read_bytes())
            else:
                raise ValueError("No image payload available.")
            return

        output_path = _resolve_plot_output_path(args)
        _write_image(result, output_path)
        print(output_path)
        return

    if args.tool_name == "plot_air_quality_history":
        if _should_stream_plot_to_stdout(args):
            _write_stdout_text(str(result))
            return

        if args.output_format == "html" or args.output is not None:
            output_path = _resolve_plot_output_path(args)
            output_path.write_text(str(result), encoding="utf-8")
            print(output_path)
            return

    if result is not None:
        _emit_formatted_text(args, result)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for direct terminal usage."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = asyncio.run(_run_command(args))
    if _is_error_result(result):
        print(result, file=sys.stderr)
        return 1
    _emit_result(args, result)
    return 0
