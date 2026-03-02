"""Go type definitions generation"""

from typing import Any

from ..utils import camel2pascal
from .utils import create_comment, decode_type


def generate_enum_type(name: str, schemas: list[dict]) -> str:
    """Generate a Go string enum type from oneOf string schemas or a single string schema"""
    lines = []
    # Check for description on the type itself
    lines.append(f"type {name} string\n")
    lines.append("const (")
    for schema in schemas:
        if "description" in schema:
            for cline in create_comment(schema["description"], "\t").splitlines():
                lines.append(cline)
        for val in schema.get("enum", []):
            const_name = name + camel2pascal(val)
            lines.append(f'\t{const_name} {name} = "{val}"')
    lines.append(")")
    return "\n".join(lines)


def collect_union_fields(
    schema: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    """Collect all properties from a union (oneOf) schema.

    Returns (all_properties, common_required_fields) where common_required_fields
    are fields required in ALL variants.
    """
    all_variants = schema["oneOf"]

    common_required: set[str] | None = None
    for variant in all_variants:
        required = set(variant.get("required", []))
        if common_required is None:
            common_required = required
        else:
            common_required &= required

    all_properties: dict[str, Any] = {}
    for variant in all_variants:
        for prop_name, prop_schema in variant.get("properties", {}).items():
            if prop_name not in all_properties:
                all_properties[prop_name] = prop_schema

    return all_properties, common_required or set()


def generate_struct_fields(properties: dict[str, Any], required_fields: set[str] | None) -> str:
    """Generate Go struct fields from a properties dict."""
    lines = []
    for prop_name, prop_schema in properties.items():
        go_type, is_optional = decode_type(prop_schema)
        exported_name = camel2pascal(prop_name)

        if required_fields is None:
            # All fields from schema's "required" list are already handled by is_optional
            is_field_optional = is_optional
        else:
            # For union types: field is optional if not in all variants' required lists
            is_field_optional = is_optional or (prop_name not in required_fields)

        if "description" in prop_schema:
            for cline in create_comment(prop_schema["description"], "\t").splitlines():
                lines.append(cline)

        if is_field_optional:
            if (
                not go_type.startswith("*")
                and not go_type.startswith("[]")
                and not go_type.startswith("map[")
            ):
                go_type = f"*{go_type}"
            lines.append(f'\t{exported_name} {go_type} `json:"{prop_name},omitempty"`')
        else:
            lines.append(f'\t{exported_name} {go_type} `json:"{prop_name}"`')
    return "\n".join(lines)


def generate_object_type(
    name: str, schema: dict[str, Any], required_fields: set[str] | None = None
) -> str:
    """Generate a Go struct type from an object schema."""
    lines = []
    if "description" in schema:
        for cline in create_comment(schema["description"]).splitlines():
            lines.append(cline)
    lines.append(f"type {name} struct {{")

    properties = schema.get("properties", {})
    if required_fields is None:
        required_fields = set(schema.get("required", []))

    fields = generate_struct_fields(properties, required_fields)
    if fields:
        lines.append(fields)
    lines.append("}")
    return "\n".join(lines)


def generate_union_type(name: str, schema: dict[str, Any]) -> str:
    """Generate a Go struct type from a oneOf object union schema.

    Uses a flat struct with all fields from all variants. The Kind field
    indicates which variant is active.
    """
    all_properties, common_required = collect_union_fields(schema)

    if "description" in schema:
        comment = create_comment(schema["description"])
    else:
        comment = ""

    lines = []
    if comment:
        for cline in comment.splitlines():
            lines.append(cline)
    lines.append(f"type {name} struct {{")

    fields = generate_struct_fields(all_properties, common_required)
    if fields:
        lines.append(fields)
    lines.append("}")
    return "\n".join(lines)


def has_pair_types(methods: list[dict]) -> bool:
    """Check if any method return values or parameters use the Pair[A, B] tuple type"""

    def check_schema(s: dict) -> bool:
        if s.get("type") == "array" and isinstance(s.get("items"), list):
            return True
        return False

    for method in methods:
        result_schema = method.get("result", {}).get("schema", {})
        if check_schema(result_schema):
            return True
        for param in method.get("params", []):
            if check_schema(param.get("schema", {})):
                return True
    return False


def generate_type(name: str, schema: dict[str, Any]) -> str:
    """Generate a Go type definition from a JSON schema type"""
    if "oneOf" in schema:
        if all(typ.get("type") == "string" for typ in schema["oneOf"]):
            return generate_enum_type(name, schema["oneOf"])
        return generate_union_type(name, schema)
    if schema.get("type") == "string":
        return generate_enum_type(name, [schema])
    if schema.get("type") == "object":
        return generate_object_type(name, schema)
    raise ValueError(f"Unknown schema: {schema}")
