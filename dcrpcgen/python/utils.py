"""Utilities for Python code generation."""


def create_comment(text: str, indentation: str = "", docstr: bool = False) -> str:
    """Generate a Python comment"""
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
