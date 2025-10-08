"""Java code generation"""

from argparse import Namespace
from pathlib import Path
from typing import Any

from ..utils import snake2camel
from .templates import get_template
from .types import generate_types
from .utils import create_comment, decode_type, get_banner

BANNER = get_banner()


def java_cmd(args: Namespace) -> None:
    """Generate JSON-RPC client for the Java programming language"""
    root_package = "chat.delta"
    root_folder = Path(args.folder, *root_package.split("."))

    rpc_package = root_package + ".rpc"
    rpc_folder = root_folder / "rpc"
    rpc_folder.mkdir(parents=True, exist_ok=True)

    types_folder = rpc_folder / "types"
    types_folder.mkdir(parents=True, exist_ok=True)
    schemas = args.openrpc_spec["components"]["schemas"]
    generate_types(types_folder, rpc_package + ".types", schemas)

    util_package = root_package + ".util"
    util_folder = root_folder / "util"
    util_folder.mkdir(parents=True, exist_ok=True)
    generate_util(util_folder, util_package)

    path = rpc_folder / "Rpc.java"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("Rpc.java.j2")
        output.write(
            template.render(
                banner=BANNER,
                package=rpc_package,
                methods=args.openrpc_spec["methods"],
                generate_method=generate_method,
            )
        )

    path = rpc_folder / "RpcException.java"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("RpcException.java.j2")
        output.write(template.render(package=rpc_package, banner=BANNER))

    path = rpc_folder / "BaseTransport.java"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("BaseTransport.java.j2")
        output.write(
            template.render(
                package=rpc_package, util_package=util_package, banner=BANNER
            )
        )


def generate_method(method: dict[str, Any]) -> str:
    """Generate a RPC method"""
    assert method["paramStructure"] == "by-position"
    params = method["params"]
    result_type = decode_type(method["result"]["schema"])[0]
    name = method["name"]
    text = ""
    if "description" in method:
        text += create_comment(method["description"], "  ")
    text += f"  public {result_type} {snake2camel(name)}("
    text += ", ".join(
        decode_type(param["schema"])[0] + " " + param["name"] for param in params
    )
    text += ") throws RpcException {\n"
    args = ", ".join(
        [f'"{name}"'] + [f'mapper.valueToTree({param["name"]})' for param in params]
    )
    if result_type == "void":
        text += f"    transport.call({args});\n"
    else:
        reftype = f"new TypeReference<{result_type}>(){{}}"
        text += f"    return transport.callForResult({reftype}, {args});\n"
    text += "  }\n"
    return text


def generate_util(folder: Path, package: str) -> None:
    """Generate util package's classes"""
    path = folder / "ListenableFuture.java"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("ListenableFuture.java.j2")
        output.write(template.render(package=package, banner=BANNER))

    path = folder / "SettableFuture.java"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("SettableFuture.java.j2")
        output.write(template.render(package=package, banner=BANNER))
