"""Python code generation"""

from argparse import Namespace
from pathlib import Path
from typing import Any

from ..utils import camel2snake
from .templates import get_template
from .types import decode_type, generate_types
from .utils import create_comment


def python_cmd(args: Namespace) -> None:
    """Generate JSON-RPC client for the Python programming language"""
    root_folder = Path(args.folder)
    root_folder.mkdir(parents=True, exist_ok=True)

    path = root_folder / "types.py"
    print(f"Generating {path}")
    generate_types(path, args.openrpc_spec["components"]["schemas"])

    path = root_folder / "rpc.py"
    print(f"Generating {path}")
    generate_methods(path, args.openrpc_spec["methods"])

    path = root_folder / "transport.py"
    print(f"Generating {path}")
    generate_transport(path)

    path = root_folder / "_utils.py"
    print(f"Generating {path}")
    generate_utils(path)


def generate_methods(path: Path, methods: dict[str, Any]) -> str:
    """Generate Rpc class"""
    with path.open("w", encoding="utf-8") as output:
        template = get_template("rpc.py.j2")
        output.write(
            template.render(
                methods=methods,
                generate_method=generate_method,
            )
        )


def generate_method(method: dict[str, Any]) -> str:
    """Generate a rpc module"""
    assert method["paramStructure"] == "by-position"
    params = method["params"]
    params_types = {param["name"]: decode_type(param["schema"]) for param in params}
    result_type = decode_type(method["result"]["schema"])
    name = method["name"]
    tab = "    "
    text = ""
    text += f"{tab}def {name}("
    text += ", ".join(
        f'{camel2snake(param["name"])}: {params_types[param["name"]]}'
        for param in params
    )
    text += f") -> {result_type}:\n"
    if "description" in method:
        text += create_comment(method["description"], tab * 2, docstr=True)

    args = [f'"{name}"']
    for param in params:
        param_name = camel2snake(param["name"])
        if params_types[param["name"]] in (
            "bool",
            "int",
            "float",
            "str",
            "Optional[bool]",
            "Optional[int]",
            "Optional[float]",
            "Optional[str]",
            "list[bool]",
            "list[int]",
            "list[float]",
            "list[str]",
            "dict[Any, Optional[str]]",
            "dict[Any, str]",
            "tuple[float, float]",
        ):
            args.append(param_name)
        else:
            args.append(f"_wrap({param_name})")

    rtn = "" if result_type == "None" else "return "
    stmt = f'transport.call({", ".join(args)})'
    text += f"{tab*2}{rtn}{stmt}\n"
    return text


def generate_transport(path: Path) -> str:
    """Generate transport module"""
    with path.open("w", encoding="utf-8") as output:
        template = get_template("transport.py.j2")
        output.write(template.render())


def generate_utils(path: Path) -> str:
    """Generate utils module"""
    with path.open("w", encoding="utf-8") as output:
        template = get_template("utils.py.j2")
        output.write(template.render())
