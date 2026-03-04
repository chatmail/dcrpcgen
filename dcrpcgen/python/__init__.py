"""Python code generation"""

import argparse
from pathlib import Path
from typing import Any

from ..utils import add_subcommand
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

    schemas = args.openrpc_spec["components"]["schemas"]
    generate_types(folder, schemas)

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


def generate_method(method: dict[str, Any]) -> str:
    """Generate a Python async RPC method"""
    assert method["paramStructure"] == "by-position"
    params = method["params"]
    result_type, _ = decode_type(method["result"]["schema"])
    name = method["name"]

    param_list = ", ".join(
        f'{param["name"]}: {decode_type(param["schema"])[0]}' for param in params
    )
    if param_list:
        param_list = ", " + param_list

    call_args = ", ".join([f'"{name}"'] + [param["name"] for param in params])

    if result_type == "None":
        text = f"    async def {name}(self{param_list}) -> None:\n"
        if "description" in method:
            text += create_comment(method["description"].strip(), "        ")
        text += f"        await self._transport.call({call_args})\n"
    else:
        text = f"    async def {name}(self{param_list}) -> {result_type}:\n"
        if "description" in method:
            text += create_comment(method["description"].strip(), "        ")
        text += (
            f"        return cast({result_type}, await self._transport.call_result({call_args}))\n"
        )
    return text
