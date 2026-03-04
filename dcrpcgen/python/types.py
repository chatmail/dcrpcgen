"""Python type definitions generation"""

from pathlib import Path
from typing import Any

from ..utils import camel2pascal, camel2snake
from .templates import get_template
from .utils import create_comment, decode_type, get_banner


def get_subtype_name(schema: dict[str, Any]) -> str:
    """Get the kind discriminator value from a union variant schema"""
    kind = schema["properties"]["kind"]
    assert kind["type"] == "string"
    assert len(kind["enum"]) == 1
    return kind["enum"][0]


def get_variant_class_name(parent_name: str, variant: dict[str, Any]) -> str:
    """Get the class name for a union variant"""
    return parent_name + camel2pascal(get_subtype_name(variant))


def generate_types(path: Path, schemas: dict[str, Any]) -> None:
    """Generate Python type definitions from RPC schema"""
    items = []
    for name, schema in schemas.items():
        if "oneOf" in schema:
            if all(typ["type"] == "string" for typ in schema["oneOf"]):
                items.append(_generate_strenum(name, schema["oneOf"]))
            else:
                items.append(_generate_union_type(name, schema))
        elif schema["type"] == "string":
            items.append(_generate_strenum(name, [schema]))
        elif schema["type"] == "object":
            items.append(_generate_class(name, schema))
        else:
            raise ValueError(f"Unknown schema: {schema}")

    banner = get_banner()
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("types.py.j2")
        output.write(
            template.render(
                banner=banner,
                items=items,
            )
        )


def _generate_strenum(name: str, schemas: list[dict]) -> str:
    """Generate a StrEnum class"""
    print("Generating", name)
    template = get_template("StrEnumTemplate.py.j2")
    return template.render(
        name=name,
        schemas=schemas,
        create_comment=create_comment,
        camel2snake=camel2snake,
    )


def _generate_union_type(name: str, schema: dict[str, Any]) -> str:
    """Generate pydantic union type (discriminated union)"""
    print("Generating", name)
    template = get_template("UnionType.py.j2")
    return template.render(
        name=name,
        schema=schema,
        create_comment=create_comment,
        get_variant_class_name=get_variant_class_name,
        generate_variant=_generate_variant,
        decode_type=decode_type,
        camel2snake=camel2snake,
    )


def _generate_variant(variant: dict[str, Any], parent_name: str) -> str:
    """Generate a pydantic BaseModel for one variant of a union type"""
    class_name = get_variant_class_name(parent_name, variant)
    print(f"  Generating {class_name}")
    template = get_template("VariantClass.py.j2")
    return template.render(
        class_name=class_name,
        variant=variant,
        create_comment=create_comment,
        decode_type=decode_type,
        camel2snake=camel2snake,
        get_subtype_name=get_subtype_name,
    )


def _generate_class(name: str, schema: dict[str, Any]) -> str:
    """Generate a normal pydantic BaseModel class"""
    print("Generating", name)
    template = get_template("NormalClass.py.j2")
    return template.render(
        name=name,
        schema=schema,
        create_comment=create_comment,
        decode_type=decode_type,
        camel2snake=camel2snake,
    )
