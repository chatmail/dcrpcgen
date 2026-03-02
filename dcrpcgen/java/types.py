"""Classes in the "types" package"""

from pathlib import Path
from typing import Any

from .templates import get_template
from .utils import create_comment, decode_type, get_banner

BANNER = get_banner()


def generate_enum(folder: Path, package: str, name: str, schemas: list[dict]) -> None:
    """Generate a Java enumeration"""
    path = folder / f"{name}.java"
    with path.open("w", encoding="utf-8") as output:
        print("Generating", path)
        template = get_template("EnumTemplate.java.j2")
        output.write(
            template.render(
                banner=BANNER,
                package=package,
                name=name,
                schemas=schemas,
                create_comment=create_comment,
            )
        )


def generate_supertype(folder: Path, package: str, name: str, schema: dict[str, Any]) -> None:
    """Generate abstract super-class"""
    path = folder / f"{name}.java"
    with path.open("w", encoding="utf-8") as output:
        print("Generating", path)
        template = get_template("SuperClass.java.j2")
        output.write(
            template.render(
                banner=BANNER,
                package=package,
                name=name,
                schema=schema,
                create_comment=create_comment,
                get_subtype_name=get_subtype_name,
                generate_subtype=generate_subtype,
            )
        )


def get_subtype_name(schema: dict[str, Any]) -> str:
    """Get class name from the given child class schema"""
    assert schema["type"] == "object"
    kind = schema["properties"]["kind"]
    assert kind["type"] == "string"
    assert len(kind["enum"]) == 1
    name = kind["enum"][0]
    return name[0].upper() + name[1:]


def generate_subtype(schema: dict[str, Any], parent: str) -> str:
    """Generate child inner class"""
    name = get_subtype_name(schema)
    print(f"  Generating {parent}.{name}")
    if desc := schema.get("description"):
        class_docs = create_comment(desc)
    else:
        class_docs = ""
    text = f"{class_docs}  public static class {name} extends {parent} {{\n"
    text += generate_properties(schema["properties"], True)
    text += "  }"
    return text


def generate_class(folder: Path, package: str, name: str, schema: dict[str, Any]) -> None:
    """Generate normal standalone class type (no child class, no super-class)"""
    assert schema["type"] == "object"
    path = folder / f"{name}.java"
    with path.open("w", encoding="utf-8") as output:
        print("Generating", path)
        template = get_template("NormalClass.java.j2")
        output.write(
            template.render(
                banner=BANNER,
                package=package,
                name=name,
                schema=schema,
                create_comment=create_comment,
                generate_properties=generate_properties,
            )
        )


def generate_properties(properties: dict[str, Any], is_subclass: bool) -> str:
    """Generate class fields"""
    tab = "    " if is_subclass else "  "
    text = ""
    for property_name, property_desc in properties.items():
        if is_subclass and property_name == "kind":
            continue
        typ, optional = decode_type(property_desc)
        if desc := property_desc.get("description"):
            text += create_comment(desc, tab)
        if mini := property_desc.get("minimum"):
            minimum = create_comment(f"minimum value: {mini}", " ")
        else:
            minimum = "\n"
        if optional:
            jackson_pack = "com.fasterxml.jackson.annotation"
            text += f"{tab}@{jackson_pack}.JsonSetter(nulls = {jackson_pack}.Nulls.SET)\n"
        text += f"{tab}public {typ} {property_name};{minimum}"
    return text


def generate_types(folder: Path, package: str, schemas: dict[str, Any]) -> None:
    """Generate classes and enumerations from RPC type definitions"""
    for name, schema in schemas.items():
        if "oneOf" in schema:
            if all(typ["type"] == "string" for typ in schema["oneOf"]):
                # Simple enumeration consisting only of various string types.
                generate_enum(folder, package, name, schema["oneOf"])
            else:
                # Union type.
                generate_supertype(folder, package, name, schema)
        elif schema["type"] == "string":
            generate_enum(folder, package, name, [schema])
        elif schema["type"] == "object":
            generate_class(folder, package, name, schema)
        else:
            raise ValueError(f"Unknow schema: {schema}")

    path = folder / "Pair.java"
    with path.open("w", encoding="utf-8") as output:
        print(f"Generating {path}")
        template = get_template("Pair.java.j2")
        output.write(template.render(package=package, banner=BANNER))
