"""Python code generation"""

import argparse
from pathlib import Path
from typing import Any

from ..utils import add_subcommand, camel2snake
from .templates import get_template
from .types import generate_types
from .utils import create_comment, decode_type, get_banner

BANNER = get_banner()


def add_python_cmd(subparsers: argparse._SubParsersAction, base: argparse.ArgumentParser) -> None:
    add_subcommand(subparsers, base, python_cmd)


def python_cmd(args: argparse.Namespace) -> None:
    """Generate JSON-RPC client for the Python programming language"""
    folder = Path(args.folder)
    folder.mkdir(parents=True, exist_ok=True)

    generate_types(folder / "types.py", args.openrpc_spec["components"]["schemas"])

    path = folder / "rpc.py"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("rpc.py.j2")
        output.write(
            template.render(
                banner=BANNER,
                methods=args.openrpc_spec["methods"],
                generate_method=generate_method,
            )
        )

    path = folder / "transport.py"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("transport.py.j2")
        output.write(template.render())


def generate_method(method: dict[str, Any]) -> str:
    """Generate a Python RPC method"""
    assert method["paramStructure"] == "by-position"
    params = method["params"]
    params_types = {param["name"]: decode_type(param["schema"]) for param in params}
    result_type = decode_type(method["result"]["schema"])
    name = method["name"]
    tab = "    "

    # Build method signature with snake_case parameter names
    param_sig = ", ".join(
        f'{camel2snake(param["name"])}: {params_types[param["name"]]}' for param in params
    )
    if param_sig:
        param_sig = ", " + param_sig

    text = f"{tab}def {name}(self{param_sig}) -> {result_type}:\n"
    if "description" in method:
        text += create_comment(method["description"], tab * 2, docstr=True)

    # Build call arguments, wrapping complex types with _wrap()
    _primitive_types = frozenset(
        {
            "bool",
            "int",
            "float",
            "str",
            "None",
            "Optional[bool]",
            "Optional[int]",
            "Optional[float]",
            "Optional[str]",
            "list[bool]",
            "list[int]",
            "list[float]",
            "list[str]",
            "dict[str, str]",
            "dict[str, int]",
            "dict[str, bool]",
        }
    )
    call_args = [f'"{name}"']
    for param in params:
        param_name = camel2snake(param["name"])
        if params_types[param["name"]] in _primitive_types:
            call_args.append(param_name)
        else:
            call_args.append(f"_wrap({param_name})")

    stmt = f'self.transport.call({", ".join(call_args)})'
    if result_type == "None":
        text += f"{tab * 2}{stmt}\n"
    else:
        text += f"{tab * 2}return TypeAdapter({result_type}).validate_python({stmt})\n"
    return text
