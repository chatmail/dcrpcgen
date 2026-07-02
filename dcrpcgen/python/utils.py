"""Utilities for Python code generation."""

from typing import Any


def create_comment(text: str, indentation: str = "", docstr: bool = False) -> str:
    """Generate a Python comment"""
    text = (
        text.replace("Self::", "Rpc.")
        .replace("CommandApi::", "Rpc.")
        .replace("types::events::EventType::IncomingMsg", "EventTypeIncomingMsg")
        .replace("`MsgsChanged`", "`EventTypeMsgsChanged`")
        .replace("::", ".")
    )
    if docstr:
        if "\n" not in text:
            return f'{indentation}"""{text.strip()}"""\n'

        comment = f'{indentation}"""\n'
        for line in text.split("\n"):
            comment += f"{indentation}{line.strip()}\n"
        return comment + f'{indentation}"""\n'

    if "\n" not in text:
        return f"{indentation}# {text.strip()}\n"

    comment = ""
    for line in text.split("\n"):
        comment += f"{indentation}# {line.strip()}\n"
    return comment


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
