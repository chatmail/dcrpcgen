"""Python code generation"""

import argparse
from pathlib import Path

import black
import isort

from ..utils import add_subcommand
from .methods import generate_method
from .templates import get_template
from .types import TypeGenerator


def add_python_cmd(subparsers: argparse._SubParsersAction, base: argparse.ArgumentParser) -> None:
    add_subcommand(subparsers, base, python_cmd)


def python_cmd(args: argparse.Namespace) -> None:
    """Generate JSON-RPC client for the Python programming language"""
    root_folder = Path(args.folder)
    root_folder.mkdir(parents=True, exist_ok=True)

    methods = args.openrpc_spec["methods"]
    typegen = TypeGenerator(args.openrpc_spec["components"]["schemas"], methods)

    path = root_folder / "types.py"
    print(f"Generating {path}")
    with path.open("w", encoding="utf-8") as output:
        output.write(_format(get_template("types.py.j2").render(generator=typegen)))

    path = root_folder / "rpc.py"
    print(f"Generating {path}")
    with path.open("w", encoding="utf-8") as output:
        output.write(
            _format(
                get_template("rpc.py.j2").render(
                    methods=methods, generate_method=generate_method, typegen=typegen
                )
            )
        )

    path = root_folder / "transport.py"
    print(f"Generating {path}")
    with path.open("w", encoding="utf-8") as output:
        output.write(_format(get_template("transport.py.j2").render()))

    path = root_folder / "_utils.py"
    print(f"Generating {path}")
    with path.open("w", encoding="utf-8") as output:
        output.write(_format(get_template("_utils.py.j2").render()))


def _format(code: str) -> str:
    return black.format_str(isort.code(code), mode=black.FileMode(line_length=100))
