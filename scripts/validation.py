"""Required runtime checks, including when Python removes assert statements."""


class ValidationError(ValueError):
    """A required gate rejected its input, distinct from decoding or parsing failures."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)
