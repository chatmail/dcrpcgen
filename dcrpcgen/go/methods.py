from typing import Any

from ..utils import snake2pascal
from .templates import get_template
from .utils import create_comment, decode_type


def method_returns_union(method: dict[str, Any], union_types: set[str]) -> bool:
    """Return True if the method's result type is (or is an array/map of) a union type."""
    result_schema = method.get("result", {}).get("schema", {})
    result_type, _ = decode_type(result_schema)
    if result_type.lstrip("*") in union_types:
        return True
    if result_schema.get("type") == "array" and isinstance(result_schema.get("items"), dict):
        item_ref = result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
        if item_ref in union_types:
            return True
    if isinstance(result_schema.get("additionalProperties"), dict):
        val_ref = (
            result_schema["additionalProperties"]
            .get("$ref", "")
            .removeprefix("#/components/schemas/")
        )
        if val_ref in union_types:
            return True
    return False


def generate_method(method: dict[str, Any], union_types: set[str] | None = None) -> str:
    """Generate a Go RPC method on the Rpc struct"""
    union_types = union_types or set()
    assert method["paramStructure"] == "by-position"
    params = method["params"]
    result_schema = method["result"]["schema"]
    result_type, _ = decode_type(result_schema)
    name = method["name"]
    go_name = snake2pascal(name)

    text = ""
    if "description" in method:
        text += create_comment(method["description"].strip())

    param_list = ", ".join(f"{param['name']} {decode_type(param['schema'])[0]}" for param in params)
    call_args = ", ".join([f'"{name}"'] + [param["name"] for param in params])

    if result_type == "void":
        text += f"func (rpc *Rpc) {go_name}({param_list}) error {{\n"
        text += f"\treturn rpc.Transport.Call(rpc.Context, {call_args})\n"
        text += "}"
    elif result_type.lstrip("*") in union_types:
        # Return type is a union interface; use json.RawMessage for unmarshaling
        text += get_template("rpc_method_return_pointer.go.j2").render(
            name=go_name, param_list=param_list, result_type=result_type, call_args=call_args
        )
    elif (
        result_schema.get("type") == "array"
        and isinstance(result_schema.get("items"), dict)
        and result_schema["items"].get("$ref", "").removeprefix("#/components/schemas/")
        in union_types
    ):
        # Return type is []UnionType; unmarshal each element individually
        text += get_template("rpc_method_return_array.go.j2").render(
            name=go_name,
            param_list=param_list,
            item_type=result_schema["items"]["$ref"].removeprefix("#/components/schemas/"),
            call_args=call_args,
        )
    elif (
        isinstance(result_schema.get("additionalProperties"), dict)
        and result_schema["additionalProperties"]
        .get("$ref", "")
        .removeprefix("#/components/schemas/")
        in union_types
    ):
        # Return type is map[string]UnionType; unmarshal each value individually
        text += get_template("rpc_method_return_map.go.j2").render(
            name=go_name,
            param_list=param_list,
            val_type=result_schema["additionalProperties"]["$ref"].removeprefix(
                "#/components/schemas/"
            ),
            call_args=call_args,
        )
    else:
        text += get_template("rpc_method_return_simple.go.j2").render(
            name=go_name, param_list=param_list, result_type=result_type, call_args=call_args
        )
    return text
