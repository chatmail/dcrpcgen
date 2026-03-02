"""Go code generation"""

from argparse import Namespace
from pathlib import Path
from typing import Any

from .templates import get_template
from .types import generate_type, has_pair_types
from .utils import create_comment, decode_type, get_banner, snake2pascal

BANNER = get_banner()


def go_cmd(args: Namespace) -> None:
    """Generate JSON-RPC client for the Go programming language"""
    package_path = getattr(args, "package_path", "deltachat-rpc-client")
    folder = Path(args.folder)
    folder.mkdir(parents=True, exist_ok=True)

    schemas = args.openrpc_spec["components"]["schemas"]
    methods = args.openrpc_spec["methods"]

    # Generate types.go
    type_defs = [generate_type(name, schema) for name, schema in schemas.items()]
    uses_pairs = has_pair_types(methods)

    path = folder / "types.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("types.go.j2")
        output.write(
            template.render(
                banner=BANNER,
                type_defs=type_defs,
                has_pairs=uses_pairs,
            )
        )

    # Generate rpc.go
    path = folder / "rpc.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("rpc.go.j2")
        output.write(
            template.render(
                banner=BANNER,
                package_path=package_path,
                methods=methods,
                generate_method=generate_method,
            )
        )

    # Generate transport/
    transport_folder = folder / "transport"
    transport_folder.mkdir(parents=True, exist_ok=True)

    path = transport_folder / "transport.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("transport.go.j2")
        output.write(template.render(banner=BANNER))

    path = transport_folder / "io_transport.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("io_transport.go.j2")
        output.write(template.render(banner=BANNER))


def generate_method(method: dict[str, Any]) -> str:
    """Generate a Go RPC method on the Rpc struct"""
    assert method["paramStructure"] == "by-position"
    params = method["params"]
    result_schema = method["result"]["schema"]
    result_type, _ = decode_type(result_schema)
    name = method["name"]
    go_name = snake2pascal(name)

    text = ""
    if "description" in method:
        text += create_comment(method["description"].strip())

    param_list = ", ".join(f"{param['name']} {decode_type(param['schema'])[0]}" for param in params)

    if result_type == "void":
        text += f"func (rpc *Rpc) {go_name}({param_list}) error {{\n"
        call_args = ", ".join([f'"{name}"'] + [param["name"] for param in params])
        text += f"\treturn rpc.Transport.Call(rpc.Context, {call_args})\n"
    else:
        text += f"func (rpc *Rpc) {go_name}({param_list}) ({result_type}, error) {{\n"
        text += f"\tvar result {result_type}\n"
        call_args = ", ".join([f'"{name}"'] + [param["name"] for param in params])
        text += f"\terr := rpc.Transport.CallResult(rpc.Context, &result, {call_args})\n"
        text += "\treturn result, err\n"
    text += "}"
    return text
