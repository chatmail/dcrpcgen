"""Types generation"""

from pathlib import Path
from typing import Any

from ..utils import camel2snake
from .templates import get_template
from .utils import create_comment


def generate_strenum(name: str, schemas: list[dict]) -> str:
    """Generate a StrEnum"""
    print("Generating", name)
    template = get_template("StrEnumTemplate.py.j2")
    return template.render(
        name=name,
        schemas=schemas,
        create_comment=create_comment,
        camel2snake=camel2snake,
    )


def generate_uniontype(name: str, schema: dict[str, Any]) -> str:
    """Generate union type"""
    print("Generating", name)
    template = get_template("UnionType.py.j2")
    return template.render(
        name=name,
        schema=schema,
        create_comment=create_comment,
        get_union_type=get_union_type,
        generate_subtype=generate_subtype,
    )


def get_union_type(schema: list[dict[str, Any]], parent: str) -> str:
    """Get union type definition given list of child class schema"""
    kind_names = [parent + get_subtype_name(typ) for typ in schema]
    return " | ".join(kind_names)


def get_subtype_name(schema: dict[str, Any], capitalize=True) -> str:
    """Get class name from the given child class schema"""
    assert schema["type"] == "object"
    kind = schema["properties"]["kind"]
    assert kind["type"] == "string"
    assert len(kind["enum"]) == 1
    name = kind["enum"][0]
    return name[0].upper() + name[1:] if capitalize else name


def generate_subtype(schema: dict[str, Any], parent: str) -> str:
    """Generate child inner class"""
    name = parent + get_subtype_name(schema)
    print(f"  Generating {name}")
    props = generate_properties(schema["properties"], True)

    if not props:
        if desc := schema.get("description"):
            doc = create_comment(desc)
        else:
            doc = ""
        val = get_subtype_name(schema, False)
        return f'{doc}{name} = "{val}"'

    text = "@dataclass(kw_only=True)\n"
    text += f"class {name}:\n"
    if desc := schema.get("description"):
        text += create_comment(desc, "    ", docstr=True)
    text += props
    text += "\n"
    return text


def generate_class(name: str, schema: dict[str, Any]) -> str:
    """Generate normal standalone class type (no child class, no super-class)"""
    print("Generating", name)
    template = get_template("NormalClass.py.j2")
    return template.render(
        name=name,
        schema=schema,
        create_comment=create_comment,
        generate_properties=generate_properties,
    )


def generate_properties(properties: dict[str, Any], is_subclass: bool) -> str:
    """Generate class fields"""
    tab = "    "
    text = ""
    for property_name, property_desc in properties.items():
        if is_subclass and property_name == "kind":
            continue
        property_name = camel2snake(property_name)
        typ = decode_type(property_desc)
        if desc := property_desc.get("description"):
            text += "\n" + create_comment(desc, tab)
        if mini := property_desc.get("minimum"):
            minimum = create_comment(f"minimum value: {mini}", "  ")
        else:
            minimum = "\n"
        text += f"{tab}{property_name}: {typ}{minimum}"
    return text


def decode_type(property_desc: dict[str, Any]) -> str:
    """Decode a type, it can be a returning type or parameter type"""
    schemas_url = "#/components/schemas/"

    if "anyOf" in property_desc:
        assert len(property_desc["anyOf"]) == 2
        assert property_desc["anyOf"][1] == {"type": "null"}
        ref = property_desc["anyOf"][0]["$ref"]
        assert ref.startswith(schemas_url)
        typ = ref.removeprefix(schemas_url)
        return f"Optional[{typ}]"

    if "$ref" in property_desc:
        assert property_desc["$ref"].startswith(schemas_url)
        typ = property_desc["$ref"].removeprefix(schemas_url)
        return typ

    if property_desc["type"] == "null":
        return "None"  # only for function returning type

    if "null" in property_desc["type"]:
        assert len(property_desc["type"]) == 2
        assert property_desc["type"][1] == "null"
        property_desc["type"] = property_desc["type"][0]
        if typ := decode_type(property_desc):
            return f"Optional[{typ}]"
    elif property_desc["type"] == "boolean":
        return "bool"
    elif property_desc["type"] == "integer":
        return "int"
    elif property_desc["type"] == "number" and property_desc["format"] == "double":
        return "float"
    elif property_desc["type"] == "string":
        return "str"
    elif property_desc["type"] == "array":
        if isinstance(property_desc["items"], list):
            types = ", ".join(decode_type(x) for x in property_desc["items"])
            return f"tuple[{types}]"

        items_type = decode_type(property_desc["items"])
        return f"list[{items_type}]"
    elif "additionalProperties" in property_desc:
        additional_properties = property_desc["additionalProperties"]
        return f"dict[Any, {decode_type(additional_properties)}]"

    raise ValueError(f"Not supported: {property_desc!r}")


def generate_types(path: Path, schemas: dict[str, Any]) -> None:
    """Generate classes and enumerations from RPC type definitions"""
    items = []
    for name, schema in sorted(schemas.items(), key=lambda e: e[0]):
        if "oneOf" in schema:
            if all(typ["type"] == "string" for typ in schema["oneOf"]):
                # Simple enumeration consisting only of various string types.
                items.append(generate_strenum(name, schema["oneOf"]))
            else:
                # Union type.
                items.append(generate_uniontype(name, schema))
        elif schema["type"] == "string":
            items.append(generate_strenum(name, [schema]))
        elif schema["type"] == "object":
            items.append(generate_class(name, schema))
        else:
            raise ValueError(f"Unknow schema: {schema}")

    with path.open("w", encoding="utf-8") as output:
        output.write(f'"""Data classes and types from the JSON-RPC."""\n\n')
        output.write("from dataclasses import dataclass\n")
        output.write("from enum import StrEnum\n")
        output.write("from typing import Any, Optional, TypeAlias\n")
        output.write("\n\n")
        output.write("\n\n".join(items))
