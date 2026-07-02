"""Python type definitions generation"""

from typing import Any

from ..utils import camel2pascal, camel2snake, get_variant_kind
from .templates import get_template
from .utils import create_comment, decode_type


def _generate_enum_type(name: str, schemas: list[dict]) -> str:
    print("Generating", name)
    template = get_template("StrEnumTemplate.py.j2")
    return template.render(
        name=name,
        schemas=schemas,
        create_comment=create_comment,
        camel2snake=camel2snake,
    )


def _generate_object_type(name: str, schema: dict[str, Any]) -> str:
    """Generate normal standalone class type (no child class, no super-class)"""
    print("Generating", name)
    template = get_template("NormalClass.py.j2")
    return template.render(
        name=name,
        schema=schema,
        create_comment=create_comment,
        generate_properties=_generate_properties,
    )


def _generate_union_type(name: str, schema: dict[str, Any], export_names: set[str]) -> str:
    """Generate a per-variant class and union type alias."""
    print("Generating", name)

    def get_union_type(parent: str, schema: list[dict[str, Any]]) -> str:
        variant_names = [parent + camel2pascal(get_variant_kind(typ)) for typ in schema]
        return " | ".join(variant_names)

    def generate_unmarshal_hook(name: str, variants: list[dict[str, Any]]) -> str:
        lines = []
        func_name = f"_unmarshal{name}"
        lines.append(f"def {func_name}(data: dict) -> {name}:")
        lines.append('    kind = data.pop("kind")')
        lines.append("    match kind:")
        for variant in variants:
            kind = get_variant_kind(variant)
            variant_name = name + camel2pascal(kind)
            lines.append(f'        case "{kind}":')
            if len(variant["properties"]) > 1:
                lines.append(f"            return _from_dict({variant_name}, data)")
            else:
                lines.append("            return kind")
        lines.append("        case _:")
        lines.append(f'            raise ValueError(f"Unknow {name} kind: {{kind}}")')
        lines.append(f"\n\n_config.type_hooks[{name}] = {func_name}")
        export_names.add(func_name)
        return "\n".join(lines)

    return get_template("UnionType.py.j2").render(
        name=name,
        schema=schema,
        create_comment=create_comment,
        get_union_type=get_union_type,
        generate_variant=_generate_variant_class,
        generate_unmarshal_hook=generate_unmarshal_hook,
    )


def _generate_variant_class(parent: str, schema: dict[str, Any]) -> str:
    """Generate variant class"""
    kind = get_variant_kind(schema)
    name = parent + camel2pascal(kind)
    print(f"  Generating {name}")
    props = _generate_properties(schema["properties"], True)

    if not props:
        if desc := schema.get("description"):
            doc = create_comment(desc)
        else:
            doc = ""
        return f'{doc}{name} = Literal["{kind}"]'

    text = "@dataclass(kw_only=True)\n"
    text += f"class {name}:\n"
    if desc := schema.get("description"):
        text += create_comment(desc, "    ", docstr=True)
    text += props
    text += "\n"
    return text


def _generate_properties(properties: dict[str, Any], is_subclass: bool) -> str:
    """Generate class fields"""
    tab = "    "
    text = ""
    for property_name, property_desc in properties.items():
        if is_subclass and property_name == "kind":
            continue
        property_name = camel2snake(property_name)
        typ = decode_type(property_desc)
        if typ.startswith("Optional["):
            typ += " = None"
        if desc := property_desc.get("description"):
            text += "\n" + create_comment(desc, tab)
        if mini := property_desc.get("minimum"):
            minimum = create_comment(f"minimum value: {mini}", "  ")
        else:
            minimum = "\n"
        text += f"{tab}{property_name}: {typ}{minimum}"
    return text


class TypeGenerator:
    def __init__(self, schemas: dict[str, Any], methods: list[dict[str, Any]]) -> None:
        self.schemas = schemas
        self.methods = methods

        def is_alias(schema: dict[str, Any]) -> bool:
            if "oneOf" in schema:
                return not all(typ.get("type") == "string" for typ in schema["oneOf"])
            return False

        self.dataclass_types: set[str] = {
            name
            for name, schema in schemas.items()
            if is_alias(schema) or schema.get("type") == "object"
        }

        self.alias_types: set[str] = {name for name, schema in schemas.items() if is_alias(schema)}

        self.export_names: set[str] = set()
        for name, schema in schemas.items():
            self.export_names.add(name)
            if "oneOf" in schema:
                if not all(typ.get("type") == "string" for typ in schema["oneOf"]):
                    variant_names = set(
                        name + camel2pascal(get_variant_kind(typ)) for typ in schema["oneOf"]
                    )
                    self.export_names.update(variant_names)
        self.export_names.add("_from_dict")

    def generate_type(self, name: str, schema: dict[str, Any]) -> str:
        """Generate a type definition from a JSON schema type"""
        if "oneOf" in schema:
            if all(typ.get("type") == "string" for typ in schema["oneOf"]):
                return _generate_enum_type(name, schema["oneOf"])
            return _generate_union_type(name, schema, self.export_names)
        if schema.get("type") == "string":
            return _generate_enum_type(name, [schema])
        if schema.get("type") == "object":
            return _generate_object_type(name, schema)
        raise ValueError(f"Unknow schema: {schema}")
