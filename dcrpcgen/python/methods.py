from typing import Any

from ..utils import camel2snake
from .utils import create_comment, decode_type


def generate_method(
    method: dict[str, Any], dataclass_types: set[str], alias_types: set[str]
) -> str:
    """Generate a RPC method"""
    assert method["paramStructure"] == "by-position"
    params = method["params"]
    result_schema = method["result"]["schema"]
    result_type = decode_type(result_schema)
    name = method["name"]
    tab = "    "
    text = ""
    text += f"{tab}def {name}("
    text += ", ".join(
        ["self"]
        + [f'{camel2snake(param["name"])}: {decode_type(param["schema"])}' for param in params]
    )
    text += f") -> {result_type}:\n"
    if "description" in method:
        text += create_comment(method["description"], tab * 2, docstr=True)

    args = [f'"{name}"']
    for param in params:
        param_name = camel2snake(param["name"])
        param_type = decode_type(param["schema"])
        if param_type.startswith("Optional["):
            param_type = param_type[len("Optional[") : -1]

        if (
            param_type in dataclass_types
            or (
                param["schema"].get("type") == "array"
                and isinstance(param["schema"].get("items"), dict)
                and param["schema"]["items"].get("$ref", "").removeprefix("#/components/schemas/")
                in dataclass_types
            )
            or (
                isinstance(param["schema"].get("additionalProperties"), dict)
                and param["schema"]["additionalProperties"]
                .get("$ref", "")
                .removeprefix("#/components/schemas/")
                in dataclass_types
            )
        ):
            args.append(f"_wrap({param_name})")
        else:
            args.append(param_name)

    rtn = "" if result_type == "None" else "return "
    stmt = f'self.transport.call({", ".join(args)})'
    if not rtn:
        text += f"{tab*2}{stmt}\n"
    else:
        ret = ""
        rtype = result_type
        if rtype.startswith("Optional["):
            rtype = rtype[len("Optional[") : -1]

        if rtype in alias_types:
            ret = ("" if rtype == result_type else "_result and ") + f"_unmarshal{rtype}(_result)"
        elif (
            result_schema.get("type") == "array"
            and isinstance(result_schema.get("items"), dict)
            and result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
            in alias_types
        ):
            # Return type is list[TypeAlias]
            rtype = result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
            ret = f"[_unmarshal{rtype}(_item) for _item in _result]"
        elif (
            isinstance(result_schema.get("additionalProperties"), dict)
            and result_schema["additionalProperties"]
            .get("$ref", "")
            .removeprefix("#/components/schemas/")
            in alias_types
        ):
            # Return type is dict[string, TypeAlias]
            rtype = result_schema["additionalProperties"]["$ref"].removeprefix(
                "#/components/schemas/"
            )
            ret = f"{{_key: _unmarshal{rtype}(_val) for _key, _val in _result.items()}}"
        elif rtype in dataclass_types:
            ret = ("" if rtype == result_type else "_result and ") + f"_from_dict({rtype}, _result)"
        elif (
            result_schema.get("type") == "array"
            and isinstance(result_schema.get("items"), dict)
            and result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
            in dataclass_types
        ):
            # Return type is list[dataclass]
            rtype = result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
            ret = f"[_from_dict({rtype}, _item) for _item in _result]"
        elif (
            isinstance(result_schema.get("additionalProperties"), dict)
            and result_schema["additionalProperties"]
            .get("$ref", "")
            .removeprefix("#/components/schemas/")
            in dataclass_types
        ):
            # Return type is dict[string, dataclass]
            rtype = result_schema["additionalProperties"]["$ref"].removeprefix(
                "#/components/schemas/"
            )
            ret = f"{{_key: _from_dict({rtype}, _val) for _key, _val in _result.items()}}"

        if ret:
            text += f"{tab*2}_result = {stmt}\n"
            stmt = ret
        text += f"{tab*2}return {stmt}\n"
    return text
