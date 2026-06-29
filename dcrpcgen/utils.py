"""Common utilities"""

import argparse
import re
from typing import Callable


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
    name = snake2camel(name)
    return name[0].upper() + name[1:]


def add_subcommand(
    subparsers: argparse._SubParsersAction,
    base: argparse.ArgumentParser,
    func: Callable[[argparse.Namespace], None],
) -> argparse.ArgumentParser:
    """Add function as CLI subcommand"""
    name = func.__name__
    assert name.endswith("_cmd")
    name = name[:-4]
    assert func.__doc__
    doc = (func.__doc__).strip()
    p = subparsers.add_parser(name, description=doc, help=doc, parents=[base])
    p.set_defaults(func=func)
    return p
