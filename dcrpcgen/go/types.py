"""Go type definitions generation"""

from typing import Any

from ..utils import camel2pascal
from .utils import create_comment, decode_type


def _generate_enum_type(name: str, schemas: list[dict]) -> str:
    """Generate a Go string enum type from oneOf string schemas or a single string schema"""
    lines = []
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


def _generate_struct_fields(
    properties: dict[str, Any],
    required_fields: set[str],
    union_types: set[str] | None = None,
) -> str:
    """Generate Go struct fields from a properties dict."""
    union_types = union_types or set()
    lines = []
    for prop_name, prop_schema in properties.items():
        go_type, is_optional = decode_type(prop_schema)
        exported_name = camel2pascal(prop_name)
        base_type = go_type.lstrip("*")

        if "description" in prop_schema:
            for cline in create_comment(prop_schema["description"], "\t").splitlines():
                lines.append(cline)

        if base_type in union_types:
            # Union interface fields cannot be JSON-unmarshaled directly.
            # The parent struct's UnmarshalJSON handles them.
            lines.append(f'\t{exported_name} {go_type} `json:"-"`')
        elif is_optional or prop_name not in required_fields:
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


def _generate_unmarshal_json(
    name: str,
    properties: dict[str, Any],
    required_fields: set[str],
    union_types: set[str],
    union_props: dict[str, Any],
) -> list[str]:
    """Generate a custom UnmarshalJSON method for a struct that has union-type fields."""
    lines: list[str] = []
    lines.append(f"func (s *{name}) UnmarshalJSON(data []byte) error {{")
    lines.append("\tvar raw struct {")
    for prop_name, prop_schema in properties.items():
        exported_name = camel2pascal(prop_name)
        go_type, is_optional = decode_type(prop_schema)
        base_type = go_type.lstrip("*")
        if base_type in union_types:
            lines.append(f'\t\t{exported_name} json.RawMessage `json:"{prop_name}"`')
        elif is_optional or prop_name not in required_fields:
            if not go_type.startswith(("*", "[]", "map[")):
                go_type = f"*{go_type}"
            lines.append(f'\t\t{exported_name} {go_type} `json:"{prop_name},omitempty"`')
        else:
            lines.append(f'\t\t{exported_name} {go_type} `json:"{prop_name}"`')
    lines.append("\t}")
    lines.append("\tif err := json.Unmarshal(data, &raw); err != nil {")
    lines.append("\t\treturn err")
    lines.append("\t}")
    for prop_name, prop_schema in properties.items():
        go_type, _ = decode_type(prop_schema)
        if go_type.lstrip("*") not in union_types:
            lines.append(f"\ts.{camel2pascal(prop_name)} = raw.{camel2pascal(prop_name)}")
    first_union = True
    for prop_name, prop_schema in union_props.items():
        exported_name = camel2pascal(prop_name)
        go_type, is_optional = decode_type(prop_schema)
        base_type = go_type.lstrip("*")
        if is_optional:
            lines.append(
                f'\tif len(raw.{exported_name}) > 0 && string(raw.{exported_name}) != "null" {{'
            )
            lines.append(
                f"\t\tif err := unmarshal{base_type}(raw.{exported_name}, s.{exported_name}); err != nil {{"
            )
            lines.append("\t\t\treturn err")
            lines.append("\t\t}")
            lines.append("\t}")
        else:
            err_decl = ":=" if first_union else "="
            lines.append(
                f"\terr {err_decl} unmarshal{base_type}(raw.{exported_name}, "
                f"&s.{exported_name})"
            )
            lines.append("\tif err != nil {")
            lines.append("\t\treturn err")
            lines.append("\t}")
        first_union = False
    lines.append("\treturn nil")
    lines.append("}")
    return lines


def _generate_object_type(
    name: str, schema: dict[str, Any], union_types: set[str] | None = None
) -> str:
    """Generate a Go struct type from an object schema.

    If any field references a union type, a custom UnmarshalJSON method is also generated.
    """
    union_types = union_types or set()
    required_fields = set(schema.get("required", []))
    properties = schema.get("properties", {})

    lines = []
    if "description" in schema:
        for cline in create_comment(schema["description"]).splitlines():
            lines.append(cline)
    lines.append(f"type {name} struct {{")
    fields = _generate_struct_fields(properties, required_fields, union_types)
    if fields:
        lines.append(fields)
    lines.append("}")

    # Detect fields whose base type is a union interface and need custom UnmarshalJSON
    union_props = {
        prop_name: prop_schema
        for prop_name, prop_schema in properties.items()
        if decode_type(prop_schema)[0].lstrip("*") in union_types
    }

    if union_props:
        lines.append("")
        lines.extend(
            _generate_unmarshal_json(name, properties, required_fields, union_types, union_props)
        )

    return "\n".join(lines)


def generate_variant_struct(parent_name: str, variant: dict[str, Any]) -> str:
    """Generate a concrete struct for one variant of a discriminated union type."""
    kind_val = variant["properties"]["kind"]["enum"][0]
    variant_name = parent_name + camel2pascal(kind_val)
    required_fields = set(variant.get("required", []))
    # Exclude the "kind" discriminator field; it is injected automatically by MarshalJSON
    properties = {k: v for k, v in variant.get("properties", {}).items() if k != "kind"}

    lines = []
    if "description" in variant:
        for cline in create_comment(variant["description"]).splitlines():
            lines.append(cline)
    lines.append(f"type {variant_name} struct {{")
    fields = _generate_struct_fields(properties, required_fields)
    if fields:
        lines.append(fields)
    lines.append("}")
    lines.append(f"func (*{variant_name}) is{parent_name}Variant() {{}}")
    lines.append(f'func (*{variant_name}) GetKind() string {{ return "{kind_val}" }}')
    lines.append(f"func (v *{variant_name}) MarshalJSON() ([]byte, error) {{")
    lines.append(f"\ttype alias {variant_name}")
    lines.append("\treturn json.Marshal(struct {")
    lines.append('\t\tKind string `json:"kind"`')
    lines.append("\t\talias")
    lines.append(f'\t}}{{Kind: "{kind_val}", alias: alias(*v)}})')
    lines.append("}")
    return "\n".join(lines)


def _generate_union_type(
    name: str, schema: dict[str, Any], unmarshal_types: set[str] | None = None
) -> str:
    """Generate a Go interface + per-variant structs + unmarshal helper for a union type.

    The unmarshal helper is only emitted when ``name`` is in ``unmarshal_types``
    (or when ``unmarshal_types`` is ``None``, meaning "generate all").
    """
    parts = []

    if "description" in schema:
        for cline in create_comment(schema["description"]).splitlines():
            parts.append(cline)

    # Interface declaration
    parts.append(f"type {name} interface {{")
    parts.append(f"\tis{name}Variant()")
    parts.append("\tGetKind() string")
    parts.append("}")

    # One struct per variant
    for variant in schema["oneOf"]:
        parts.append("")
        parts.append(generate_variant_struct(name, variant))

    # Unmarshal helper (switches on the "kind" discriminator) – only when needed
    if unmarshal_types is None or name in unmarshal_types:
        parts.append("")
        parts.append(f"func unmarshal{name}(data json.RawMessage, out *{name}) error {{")
        parts.append('\tvar header struct { Kind string `json:"kind"` }')
        parts.append("\tif err := json.Unmarshal(data, &header); err != nil {")
        parts.append("\t\treturn err")
        parts.append("\t}")
        parts.append("\tswitch header.Kind {")
        for variant in schema["oneOf"]:
            kind_val = variant["properties"]["kind"]["enum"][0]
            variant_name = name + camel2pascal(kind_val)
            parts.append(f'\tcase "{kind_val}":')
            parts.append(f"\t\tvar v {variant_name}")
            parts.append("\t\tif err := json.Unmarshal(data, &v); err != nil {")
            parts.append("\t\t\treturn err")
            parts.append("\t\t}")
            parts.append("\t\t*out = &v")
        parts.append("\tdefault:")
        parts.append(f'\t\treturn fmt.Errorf("unknown {name} variant: %q", header.Kind)')
        parts.append("\t}")
        parts.append("\treturn nil")
        parts.append("}")

    return "\n".join(parts)


def _compute_unmarshal_union_types(
    methods: list[dict[str, Any]],
    schemas: dict[str, Any],
    union_types: set[str],
) -> set[str]:
    """Return the set of union types that need an unmarshal helper.

    A union type needs its helper when it is:
    - returned directly, as an array element, or as a map value by any method, OR
    - used as a field type inside a struct (because the struct's UnmarshalJSON calls the helper).
    """
    needed: set[str] = set()

    # Methods that return union types
    for method in methods:
        result_schema = method.get("result", {}).get("schema", {})
        base_type = decode_type(result_schema)[0].lstrip("*")
        if base_type in union_types:
            needed.add(base_type)
        if result_schema.get("type") == "array" and isinstance(result_schema.get("items"), dict):
            ref = result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
            if ref in union_types:
                needed.add(ref)
        if isinstance(result_schema.get("additionalProperties"), dict):
            ref = (
                result_schema["additionalProperties"]
                .get("$ref", "")
                .removeprefix("#/components/schemas/")
            )
            if ref in union_types:
                needed.add(ref)

    # Struct fields that are of a union type
    for schema in schemas.values():
        if schema.get("type") == "object":
            for prop_schema in schema.get("properties", {}).values():
                base_type = decode_type(prop_schema)[0].lstrip("*")
                if base_type in union_types:
                    needed.add(base_type)

    return needed


class TypeGenerator:
    def __init__(self, schemas: dict[str, Any], methods: list[dict[str, Any]]) -> None:
        self.schemas = schemas
        self.methods = methods
        # Compute which schema names are discriminated union types (oneOf with objects)
        self.union_types: set[str] = {
            name
            for name, schema in schemas.items()
            if "oneOf" in schema and not all(s.get("type") == "string" for s in schema["oneOf"])
        }
        # Compute which union types actually need an unmarshal helper
        self.unmarshal_types = _compute_unmarshal_union_types(methods, schemas, self.union_types)

    def generate_type(self, name: str, schema: dict[str, Any]) -> str:
        """Generate a Go type definition from a JSON schema type"""
        if "oneOf" in schema:
            if all(typ.get("type") == "string" for typ in schema["oneOf"]):
                return _generate_enum_type(name, schema["oneOf"])
            return _generate_union_type(name, schema, self.unmarshal_types)
        if schema.get("type") == "string":
            return _generate_enum_type(name, [schema])
        if schema.get("type") == "object":
            return _generate_object_type(name, schema, self.union_types)
        raise ValueError(f"Unknown schema: {schema}")

    def has_union_types(self) -> bool:
        """Return True if there are any discriminated union types (oneOf with objects)"""
        return bool(self.union_types)

    def has_pair_types(self) -> bool:
        """Return True if any method's return values or parameters use the Pair[A, B] tuple type, return False otherwise"""

        def check_schema(s: dict) -> bool:
            return s.get("type") == "array" and isinstance(s.get("items"), list)

        for method in self.methods:
            result_schema = method.get("result", {}).get("schema", {})
            if check_schema(result_schema):
                return True
            for param in method.get("params", []):
                if check_schema(param.get("schema", {})):
                    return True
        return False

    def has_unmarshal_types(self) -> bool:
        """Return True if there is union types that need an unmarshal helper"""
        return bool(self.unmarshal_types)
