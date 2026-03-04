"""Python type definitions generation"""

from pathlib import Path
from typing import Any

from ..utils import camel2pascal
from .templates import get_template
from .utils import (
    create_comment,
    create_inline_comment,
    decode_optional_type,
    decode_type,
    get_banner,
)


def get_variant_name(parent_name: str, variant: dict[str, Any]) -> str:
    """Get the class name for a union variant"""
    kind_val = variant["properties"]["kind"]["enum"][0]
    return parent_name + camel2pascal(kind_val)


def generate_types(folder: Path, schemas: dict[str, Any]) -> None:
    """Generate Python type definitions from RPC schema"""
    banner = get_banner()
    path = folder / "types.py"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("types.py.j2")
        output.write(
            template.render(
                banner=banner,
                schemas=schemas,
                decode_type=decode_type,
                decode_optional_type=decode_optional_type,
                get_variant_name=get_variant_name,
                create_comment=create_comment,
                create_inline_comment=create_inline_comment,
            )
        )
