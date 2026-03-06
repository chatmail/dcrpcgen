"""Go code generation"""

import argparse
from pathlib import Path
from typing import Any

from ..utils import add_subcommand
from .methods import generate_method, method_returns_union
from .templates import get_template
from .types import TypeGenerator


def add_go_cmd(subparsers: argparse._SubParsersAction, base: argparse.ArgumentParser) -> None:
    add_subcommand(subparsers, base, go_cmd)


def go_cmd(args: argparse.Namespace) -> None:
    """Generate JSON-RPC client for the Go programming language"""
    folder = Path(args.folder)
    folder.mkdir(parents=True, exist_ok=True)

    methods = args.openrpc_spec["methods"]
    typegen = TypeGenerator(args.openrpc_spec["components"]["schemas"], methods)

    # Generate types.go
    path = folder / "types.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        output.write(get_template("types.go.j2").render(generator=typegen))

    # Build a union-type-aware method generator closure
    def _generate_method(method: dict[str, Any]) -> str:
        return generate_method(method, typegen.union_types)

    has_union_return = any(method_returns_union(m, typegen.union_types) for m in methods)

    # Generate rpc.go
    path = folder / "rpc.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("rpc.go.j2")
        output.write(
            template.render(
                methods=methods,
                generate_method=_generate_method,
                has_union_return=has_union_return,
            )
        )

    # Generate const.go
    path = folder / "const.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        output.write(get_template("const.go.j2").render())

    # Generate transport-related code
    path = folder / "transport.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        output.write(get_template("transport.go.j2").render())

    path = folder / "io_transport.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        output.write(get_template("io_transport.go.j2").render())
