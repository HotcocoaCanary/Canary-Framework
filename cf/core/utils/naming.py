import re


_camel_split = re.compile(r"([A-Z]+(?![a-z])|[A-Z][a-z0-9]*)")


def to_snake(name: str) -> str:
    parts = _camel_split.findall(name)
    if not parts:
        return name.lower()
    return "_".join(p.lower() for p in parts)
