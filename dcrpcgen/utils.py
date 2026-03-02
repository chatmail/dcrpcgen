"""Common utilities"""

import re


def camel2snake(name: str) -> str:
    """Convert camelCase/PascalCase string to snake_case"""
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub("__([A-Z])", r"_\1", name)
    name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.lower()


def snake2camel(name: str) -> str:
    """Convert snakeCase string to camel_case"""
    parts = name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def snake2pascal(name: str) -> str:
    """Convert snake_case to PascalCase"""
    return "".join(word.capitalize() for word in name.split("_"))


def camel2pascal(name: str) -> str:
    """Capitalize first letter of a camelCase name to make it PascalCase"""
    if not name:
        return name
    return name[0].upper() + name[1:]
