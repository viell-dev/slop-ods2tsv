"""Required runtime checks, including when Python removes assert statements."""


def require(condition, message):
    if not condition:
        raise ValueError(message)
