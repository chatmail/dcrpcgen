"""Code templates"""

from jinja2 import Environment, PackageLoader, Template

env = Environment(
    loader=PackageLoader(__name__.rsplit(".", maxsplit=1)[0], "templates")
)


def get_template(name: str) -> Template:
    """Load the template with the given filename"""
    return env.get_template(name)
