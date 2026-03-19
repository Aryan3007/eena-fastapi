"""NoSQL injection prevention - strips MongoDB operators from input."""


def sanitize_value(value: object) -> object:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {
            k: sanitize_value(v)
            for k, v in value.items()
            if not k.startswith("$")
        }
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value
