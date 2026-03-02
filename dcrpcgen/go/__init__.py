"""Go code generation"""

import argparse
from pathlib import Path
from typing import Any

from ..utils import add_subcommand, snake2pascal
from .templates import get_template
from .types import generate_type, has_pair_types
from .utils import create_comment, decode_type, get_banner

BANNER = get_banner()


def add_go_cmd(subparsers: argparse._SubParsersAction, base: argparse.ArgumentParser) -> None:
    p = add_subcommand(subparsers, base, go_cmd)
    p.add_argument(
        "--package",
        help=("Go module import path for the generated package" " (default: %(default)s)"),
        metavar="PATH",
        dest="package_path",
        default="github.com/chatmail/rpc-client-go/v2/deltachat",
    )


def go_cmd(args: argparse.Namespace) -> None:
    """Generate JSON-RPC client for the Go programming language"""
    folder = Path(args.folder)
    folder.mkdir(parents=True, exist_ok=True)

    schemas = args.openrpc_spec["components"]["schemas"]
    methods = args.openrpc_spec["methods"]

    # Compute which schema names are discriminated union types (oneOf with objects)
    union_types = {
        name
        for name, schema in schemas.items()
        if "oneOf" in schema and not all(s.get("type") == "string" for s in schema["oneOf"])
    }

    # Generate types.go
    type_defs = [generate_type(name, schema, union_types) for name, schema in schemas.items()]
    uses_pairs = has_pair_types(methods)
    has_union_types = bool(union_types)

    path = folder / "types.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("types.go.j2")
        output.write(
            template.render(
                banner=BANNER,
                type_defs=type_defs,
                has_pairs=uses_pairs,
                has_union_types=has_union_types,
            )
        )

    # Build a union-type-aware method generator closure
    def _generate_method(method: dict[str, Any]) -> str:
        return generate_method(method, union_types)

    has_union_return = any(_method_returns_union(m, union_types) for m in methods)

    # Generate rpc.go
    path = folder / "rpc.go"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("rpc.go.j2")
        output.write(
            template.render(
                banner=BANNER,
                package_path=args.package_path,
                methods=methods,
                generate_method=_generate_method,
                has_union_return=has_union_return,
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


def _method_returns_union(method: dict[str, Any], union_types: set[str]) -> bool:
    """Return True if the method's result type is (or is an array of) a union type."""
    result_schema = method.get("result", {}).get("schema", {})
    result_type, _ = decode_type(result_schema)
    if result_type.lstrip("*") in union_types:
        return True
    if result_schema.get("type") == "array" and isinstance(result_schema.get("items"), dict):
        item_ref = result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
        if item_ref in union_types:
            return True
    return False


def generate_method(method: dict[str, Any], union_types: set[str] | None = None) -> str:
    """Generate a Go RPC method on the Rpc struct"""
    union_types = union_types or set()
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
    call_args = ", ".join([f'"{name}"'] + [param["name"] for param in params])

    if result_type == "void":
        text += f"func (rpc *Rpc) {go_name}({param_list}) error {{\n"
        text += f"\treturn rpc.Transport.Call(rpc.Context, {call_args})\n"
    elif result_type.lstrip("*") in union_types:
        # Return type is a union interface; use json.RawMessage for unmarshaling
        bare_type = result_type.lstrip("*")
        text += f"func (rpc *Rpc) {go_name}({param_list}) ({result_type}, error) {{\n"
        text += "\tvar raw json.RawMessage\n"
        text += (
            f"\tif err := rpc.Transport.CallResult(rpc.Context, &raw, {call_args}); err != nil {{\n"
        )
        text += "\t\treturn nil, err\n"
        text += "\t}\n"
        text += f"\tvar result {result_type}\n"
        text += f"\terr := unmarshal{bare_type}(raw, &result)\n"
        text += "\treturn result, err\n"
    elif (
        result_schema.get("type") == "array"
        and isinstance(result_schema.get("items"), dict)
        and result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
        in union_types
    ):
        # Return type is []UnionType; unmarshal each element individually
        item_type = result_schema["items"]["$ref"].removeprefix("#/components/schemas/")
        text += f"func (rpc *Rpc) {go_name}({param_list}) ([]{item_type}, error) {{\n"
        text += "\tvar rawList []json.RawMessage\n"
        text += (
            f"\tif err := rpc.Transport.CallResult(rpc.Context, &rawList, {call_args}); "
            "err != nil {\n"
        )
        text += "\t\treturn nil, err\n"
        text += "\t}\n"
        text += f"\tresult := make([]{item_type}, len(rawList))\n"
        text += "\tfor i, raw := range rawList {\n"
        text += f"\t\tif err := unmarshal{item_type}(raw, &result[i]); err != nil {{\n"
        text += "\t\t\treturn nil, err\n"
        text += "\t\t}\n"
        text += "\t}\n"
        text += "\treturn result, nil\n"
    else:
        text += f"func (rpc *Rpc) {go_name}({param_list}) ({result_type}, error) {{\n"
        text += f"\tvar result {result_type}\n"
        text += f"\terr := rpc.Transport.CallResult(rpc.Context, &result, {call_args})\n"
        text += "\treturn result, err\n"
    text += "}"
    return text
